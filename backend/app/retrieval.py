from __future__ import annotations

import asyncio
import base64
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from .schemas import ComparisonTarget, ManualSourceImportRequest, ResearchScope, SearchProviderStatus, SourceDocument, SourceType
from .settings import AppSettings


MODEL_TARGET_NAMES = {"qwen", "deepseek", "kimi", "claude", "gemini", "gpt-4.1", "gpt-4o"}


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str
    provider: str


class SearchProvider(ABC):
    def __init__(self, info: SearchProviderStatus) -> None:
        self.info = info

    @abstractmethod
    async def collect(
        self,
        retriever: "ResearchRetriever",
        *,
        target: ComparisonTarget,
        scope: ResearchScope,
    ) -> list[SourceDocument]:
        raise NotImplementedError


class GitHubSourceProvider(SearchProvider):
    async def collect(self, retriever: "ResearchRetriever", *, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        return await retriever._fetch_github_sources(target)


class OfficialDocsSourceProvider(SearchProvider):
    async def collect(self, retriever: "ResearchRetriever", *, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        source = await retriever._fetch_docs_source(target)
        return [source] if source else []


class WebSourceProvider(SearchProvider):
    async def collect(self, retriever: "ResearchRetriever", *, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        return await retriever._fetch_web_sources(target, scope)


class CrossrefSourceProvider(SearchProvider):
    async def collect(self, retriever: "ResearchRetriever", *, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        return await retriever._fetch_crossref_sources(target, scope)


class SemanticScholarSourceProvider(SearchProvider):
    async def collect(self, retriever: "ResearchRetriever", *, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        if not retriever._semantic_scholar_api_key:
            return []
        return await retriever._fetch_semantic_scholar_sources(target, scope)


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _truncate(value: str, limit: int) -> str:
    text = _collapse_whitespace(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def _summarize_text(text: str, limit: int = 280) -> str:
    normalized = _collapse_whitespace(text)
    if not normalized:
        return "当前来源没有提取到足够可读的正文内容。"
    sentences = re.split(r"(?<=[.!?。！？])\s+", normalized)
    summary = " ".join(sentences[:2]).strip()
    return _truncate(summary or normalized, limit)


def _is_model_target(target: ComparisonTarget) -> bool:
    lowered = target.name.strip().lower()
    return lowered in MODEL_TARGET_NAMES or any(
        name in lowered for name in ("gpt", "claude", "gemini", "deepseek", "qwen", "kimi")
    )


def _target_aliases(target: ComparisonTarget) -> list[str]:
    aliases = [target.name.strip().lower()]
    if target.repo_full_name:
        repo_name = target.repo_full_name.split("/")[-1].strip().lower()
        aliases.append(repo_name)
        aliases.append(repo_name.replace("-", " "))
    if target.name.lower() == "pydanticai":
        aliases.extend(["pydantic ai", "pydantic-ai"])
    if target.name.lower() == "langgraph":
        aliases.append("lang graph")
    return [alias for alias in aliases if alias]


def _mentions_target(text: str, target: ComparisonTarget) -> bool:
    lowered = text.lower()
    return any(alias in lowered for alias in _target_aliases(target))


def _best_text_match(text: str, target: ComparisonTarget) -> int:
    lowered = text.lower()
    score = 0
    for alias in _target_aliases(target):
        if alias in lowered:
            score = max(score, len(alias))
    return score


class ResearchRetriever:
    def __init__(self, settings: AppSettings) -> None:
        self._settings = settings
        self._github_token = os.getenv("GITHUB_TOKEN")
        self._semantic_scholar_api_key = os.getenv("DEEP_RESEARCH_SEMANTIC_SCHOLAR_API_KEY")
        self._google_api_key = os.getenv("DEEP_RESEARCH_GOOGLE_CSE_API_KEY")
        self._google_cx = os.getenv("DEEP_RESEARCH_GOOGLE_CSE_CX")
        self._user_agent = "DeepResearchAgent/0.2"
        self._source_providers: list[SearchProvider] = [
            GitHubSourceProvider(
                SearchProviderStatus(id="github", label="GitHub", kind="repo", enabled=True, note="仓库元数据和 README")
            ),
            OfficialDocsSourceProvider(
                SearchProviderStatus(id="official_docs", label="Official Docs", kind="docs", enabled=True, note="官方文档主页或产品主页")
            ),
            WebSourceProvider(
                SearchProviderStatus(id="duckduckgo", label="DuckDuckGo", kind="web", enabled=True, note="开放网页发现")
            ),
            CrossrefSourceProvider(
                SearchProviderStatus(id="crossref", label="Crossref", kind="academic", enabled=True, note="开放学术元数据")
            ),
            SemanticScholarSourceProvider(
                SearchProviderStatus(
                    id="semantic_scholar",
                    label="Semantic Scholar",
                    kind="academic",
                    enabled=bool(self._semantic_scholar_api_key),
                    note="配置 API Key 后启用",
                )
            ),
        ]

    async def collect_sources(self, scope: ResearchScope) -> list[SourceDocument]:
        tasks = [self._collect_target_sources(target, scope) for target in scope.comparison_targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        deduped: dict[str, SourceDocument] = {}
        for result in results:
            if isinstance(result, Exception):
                continue
            for source in result:
                url_key = source.url.casefold()
                existing = deduped.get(url_key)
                if existing is None:
                    deduped[url_key] = source
                    continue
                deduped[url_key] = self._merge_sources(existing, source)

        ordered = list(deduped.values())
        ordered.sort(
            key=lambda item: (
                max(item.quality_score, 0.0),
                item.metadata.get("target_rank", 999),
                item.created_at,
            ),
            reverse=True,
        )
        return ordered

    def list_search_providers(self) -> list[SearchProviderStatus]:
        providers = [provider.info.model_copy(deep=True) for provider in self._source_providers]
        providers.append(
            SearchProviderStatus(
                id="google_programmable_search",
                label="Google Programmable Search",
                kind="web",
                enabled=bool(self._google_api_key and self._google_cx),
                note="提供官方凭据后启用",
            )
        )
        providers.append(
            SearchProviderStatus(
                id="google_scholar_manual",
                label="Google Scholar Manual",
                kind="manual",
                enabled=False,
                note="仅支持手动导入，不做自动抓取",
            )
        )
        providers.append(
            SearchProviderStatus(
                id="cnki_manual",
                label="CNKI Manual",
                kind="manual",
                enabled=False,
                note="仅支持手动导入，不做自动抓取",
            )
        )
        return providers

    async def import_manual_sources(
        self,
        request: ManualSourceImportRequest,
        *,
        scope: ResearchScope | None = None,
    ) -> list[SourceDocument]:
        raw_target_name = (request.target_name or "").strip()
        target_name = raw_target_name or self._infer_target_name_from_scope(scope)
        imported: list[SourceDocument] = []

        if request.url:
            source = await self._import_source_from_url(request.url.strip(), target_name=target_name, note=request.note)
            if source:
                imported.append(source)
        if request.doi:
            source = await self._import_source_from_doi(request.doi.strip(), target_name=target_name, note=request.note)
            if source:
                imported.append(source)
        if request.bibtex:
            source = await self._import_source_from_bibtex(request.bibtex, target_name=target_name, note=request.note)
            if source:
                imported.append(source)
        if request.title and not any([request.url, request.doi, request.bibtex]):
            source = await self._import_source_from_title(request.title.strip(), target_name=target_name, note=request.note)
            if source:
                imported.append(source)

        deduped: dict[str, SourceDocument] = {}
        for source in imported:
            key = source.url.casefold()
            existing = deduped.get(key)
            deduped[key] = source if existing is None else self._merge_sources(existing, source)
        return list(deduped.values())

    async def _collect_target_sources(self, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        sources: list[SourceDocument] = []
        tasks = [self._capture(provider.collect(self, target=target, scope=scope), []) for provider in self._source_providers if provider.info.enabled]
        results = await asyncio.gather(*tasks)
        for result in results:
            sources.extend(result)
        return sources

    async def _fetch_github_sources(self, target: ComparisonTarget) -> list[SourceDocument]:
        if not target.repo_full_name:
            return []

        repo_path = target.repo_full_name
        repo_data = await self._github_json(f"/repos/{repo_path}")
        if not repo_data:
            return []

        releases, readme_payload = await asyncio.gather(
            self._capture(self._github_json(f"/repos/{repo_path}/releases?per_page=5"), []),
            self._capture(self._github_json(f"/repos/{repo_path}/readme"), None),
        )

        pushed_at = repo_data.get("pushed_at")
        pushed_days = self._days_since_timestamp(pushed_at)
        release_count = len(releases) if isinstance(releases, list) else 0
        description = repo_data.get("description") or ""
        topics = repo_data.get("topics") or []
        repo_summary = (
            f"{description} {repo_data.get('stargazers_count', 0):,} stars, "
            f"{repo_data.get('forks_count', 0):,} forks, {repo_data.get('open_issues_count', 0)} open issues, "
            f"sampled {release_count} recent releases, updated {pushed_days} days ago."
        )

        sources = [
            SourceDocument(
                run_id="",
                title=f"{target.name} GitHub repository",
                url=repo_data.get("html_url") or f"https://github.com/{repo_path}",
                domain="github.com",
                source_type=SourceType.GITHUB_REPO,
                summary=_truncate(repo_summary, 320),
                snippet=_truncate("Topics: " + ", ".join(topics) if topics else description or repo_summary, 320),
                quality_score=0.9,
                tags=[target.name, "github", "repo"],
                metadata={
                    "target_name": target.name,
                    "target_rank": 0,
                    "query": target.name,
                    "repo_full_name": repo_path,
                    "stargazers_count": repo_data.get("stargazers_count", 0),
                    "forks_count": repo_data.get("forks_count", 0),
                    "open_issues_count": repo_data.get("open_issues_count", 0),
                    "release_count": release_count,
                    "days_since_push": pushed_days,
                    "language": repo_data.get("language"),
                    "license": (repo_data.get("license") or {}).get("spdx_id"),
                    "homepage": repo_data.get("homepage"),
                    "topics": topics,
                    "search_provider": "github_api",
                    "evidence_bucket": "repo_signal",
                },
            )
        ]

        if isinstance(readme_payload, dict):
            readme_text = self._decode_readme(readme_payload)
            if readme_text:
                sources.append(
                    SourceDocument(
                        run_id="",
                        title=f"{target.name} README",
                        url=(repo_data.get("html_url") or f"https://github.com/{repo_path}") + "#readme",
                        domain="github.com",
                        source_type=SourceType.README,
                        summary=_summarize_text(readme_text, 300),
                        snippet=_truncate(readme_text, 340),
                        quality_score=0.84,
                        tags=[target.name, "github", "readme"],
                        metadata={
                            "target_name": target.name,
                            "target_rank": 1,
                            "repo_full_name": repo_path,
                            "search_provider": "github_api",
                            "query": target.name,
                            "evidence_bucket": "repo_signal",
                        },
                    )
                )

        return sources

    async def _fetch_docs_source(self, target: ComparisonTarget) -> SourceDocument | None:
        docs_url = target.docs_url or target.homepage_url
        if not docs_url:
            return None
        digest = await self._fetch_page_digest(docs_url)
        if not digest:
            return None
        return SourceDocument(
            run_id="",
            title=digest["title"] or f"{target.name} official docs",
            url=docs_url,
            domain=_domain_from_url(docs_url),
            source_type=SourceType.OFFICIAL_DOC,
            summary=digest["summary"],
            snippet=digest["snippet"],
            quality_score=0.92,
            tags=[target.name, "official-docs"],
            metadata={
                "target_name": target.name,
                "target_rank": 2,
                "content_length": digest["content_length"],
                "search_provider": "official_docs",
                "query": docs_url,
                "evidence_bucket": "official_doc",
            },
        )

    async def _fetch_web_sources(self, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        query = self._build_target_query(target, scope)
        hits = await self._search_web(query)

        excluded_domains = {
            "github.com",
            _domain_from_url(target.docs_url) if target.docs_url else "",
            _domain_from_url(target.homepage_url) if target.homepage_url else "",
        }

        filtered: list[SearchHit] = []
        for hit in hits:
            domain = _domain_from_url(hit.url)
            if not domain or domain in excluded_domains:
                continue
            if not _mentions_target(f"{hit.title} {hit.snippet}", target):
                continue
            filtered.append(hit)
            if len(filtered) >= self._settings.web_results_per_target:
                break

        sources: list[SourceDocument] = []
        for index, hit in enumerate(filtered):
            digest = await self._fetch_page_digest(hit.url)
            text_for_match = f"{hit.title} {hit.snippet} {(digest or {}).get('snippet', '')}"
            if not _mentions_target(text_for_match, target):
                continue
            summary = digest["summary"] if digest else _truncate(hit.snippet, 280)
            body_snippet = digest["snippet"] if digest else _truncate(hit.snippet, 320)
            quality = 0.76 if hit.provider == "google_cse" else 0.72
            if any(keyword in hit.url for keyword in ("blog", "news", "medium")):
                quality -= 0.04
            sources.append(
                SourceDocument(
                    run_id="",
                    title=hit.title,
                    url=hit.url,
                    domain=_domain_from_url(hit.url),
                    source_type=SourceType.WEB_ARTICLE,
                    summary=summary,
                    snippet=body_snippet,
                    quality_score=max(quality, 0.55),
                    tags=[target.name, "external"],
                    metadata={
                        "target_name": target.name,
                        "target_rank": 10 + index,
                        "query": query,
                        "search_provider": hit.provider,
                        "evidence_bucket": "external_validation",
                    },
                )
            )

        return sources

    async def _fetch_academic_sources(self, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        tasks = [
            self._capture(self._fetch_crossref_sources(target, scope), []),
        ]
        if self._semantic_scholar_api_key:
            tasks.append(self._capture(self._fetch_semantic_scholar_sources(target, scope), []))

        results = await asyncio.gather(*tasks)
        sources: list[SourceDocument] = []
        for result in results:
            sources.extend(result)
        return sources

    async def _fetch_crossref_sources(self, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        params = {
            "query.title": f"{target.name} {self._academic_context(scope)}",
            "rows": 3,
            "mailto": "research-agent@example.com",
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            response = await client.get("https://api.crossref.org/works", params=params, headers={"User-Agent": self._user_agent})
            if response.status_code >= 400:
                return []
            payload = response.json()

        items = (payload.get("message") or {}).get("items") or []
        sources: list[SourceDocument] = []
        for index, item in enumerate(items):
            title = _collapse_whitespace(" ".join(item.get("title") or []))
            abstract = _collapse_whitespace(self._strip_jats(item.get("abstract") or ""))
            text = f"{title} {abstract}"
            if not _mentions_target(text, target):
                continue
            doi = item.get("DOI")
            url = f"https://doi.org/{doi}" if doi else item.get("URL")
            if not url:
                continue
            venue = _collapse_whitespace(" ".join(item.get("container-title") or []))
            year_parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
            year = year_parts[0] if year_parts else None
            snippet = _truncate(abstract or f"{title} {venue} {year or ''}", 320)
            summary = _summarize_text(abstract or title, 260)
            sources.append(
                SourceDocument(
                    run_id="",
                    title=title,
                    url=url,
                    domain=_domain_from_url(url),
                    source_type=SourceType.ACADEMIC_METADATA,
                    summary=summary,
                    snippet=snippet,
                    quality_score=0.74,
                    tags=[target.name, "academic"],
                    metadata={
                        "target_name": target.name,
                        "target_rank": 20 + index,
                        "search_provider": "crossref",
                        "query": params["query.title"],
                        "venue": venue,
                        "year": year,
                        "doi": doi,
                        "evidence_bucket": "academic_validation",
                    },
                )
            )
            if len(sources) >= 1:
                break

        return sources

    async def _fetch_semantic_scholar_sources(self, target: ComparisonTarget, scope: ResearchScope) -> list[SourceDocument]:
        headers = {"User-Agent": self._user_agent, "x-api-key": self._semantic_scholar_api_key or ""}
        params = {
            "query": f"{target.name} {self._academic_context(scope)}",
            "limit": 3,
            "fields": "title,url,abstract,year,venue,citationCount",
        }
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            response = await client.get("https://api.semanticscholar.org/graph/v1/paper/search", params=params, headers=headers)
            if response.status_code >= 400:
                return []
            payload = response.json()

        papers = payload.get("data") or []
        sources: list[SourceDocument] = []
        for index, paper in enumerate(papers):
            title = _collapse_whitespace(paper.get("title") or "")
            abstract = _collapse_whitespace(paper.get("abstract") or "")
            if not _mentions_target(f"{title} {abstract}", target):
                continue
            url = paper.get("url")
            if not url:
                continue
            sources.append(
                SourceDocument(
                    run_id="",
                    title=title,
                    url=url,
                    domain=_domain_from_url(url),
                    source_type=SourceType.SCHOLAR_PAPER,
                    summary=_summarize_text(abstract or title, 260),
                    snippet=_truncate(abstract or title, 320),
                    quality_score=0.78,
                    tags=[target.name, "academic"],
                    metadata={
                        "target_name": target.name,
                        "target_rank": 30 + index,
                        "search_provider": "semantic_scholar",
                        "query": params["query"],
                        "venue": paper.get("venue"),
                        "year": paper.get("year"),
                        "citation_count": paper.get("citationCount"),
                        "evidence_bucket": "academic_validation",
                    },
                )
            )
            if len(sources) >= 1:
                break

        return sources

    async def _search_web(self, query: str) -> list[SearchHit]:
        tasks = [
            self._capture(self._duckduckgo_search(query), []),
        ]
        if self._google_api_key and self._google_cx:
            tasks.append(self._capture(self._google_cse_search(query), []))

        results = await asyncio.gather(*tasks)
        hits: list[SearchHit] = []
        seen_urls: set[str] = set()
        for provider_hits in results:
            for hit in provider_hits:
                key = hit.url.casefold()
                if key in seen_urls:
                    continue
                seen_urls.add(key)
                hits.append(hit)
        return hits

    def _build_target_query(self, target: ComparisonTarget, scope: ResearchScope) -> str:
        dimension_hint = " ".join(scope.comparison_dimensions[:2]).strip()
        target_phrase = f'"{target.name}"'

        if _is_model_target(target):
            query = f"{target_phrase} API pricing benchmark context window rate limit"
        else:
            query = f"{target_phrase} agent framework production observability state management"

        if dimension_hint:
            query = f"{query} {dimension_hint}"
        if scope.context:
            query = f"{query} {scope.context}"
        return query

    def _academic_context(self, scope: ResearchScope) -> str:
        parts = ["agent framework"]
        if scope.comparison_dimensions:
            parts.extend(scope.comparison_dimensions[:2])
        return " ".join(parts)

    async def _github_json(self, path: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": self._user_agent,
        }
        if self._github_token:
            headers["Authorization"] = f"Bearer {self._github_token}"

        async with httpx.AsyncClient(
            base_url="https://api.github.com",
            follow_redirects=True,
            timeout=httpx.Timeout(25.0, connect=10.0),
        ) as client:
            response = await client.get(path, headers=headers)
            if response.status_code >= 400:
                return None
            return response.json()

    async def _duckduckgo_search(self, query: str) -> list[SearchHit]:
        headers = {"User-Agent": self._user_agent}
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            response = await client.get("https://html.duckduckgo.com/html/", params={"q": query}, headers=headers)
            if response.status_code >= 400:
                return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: list[SearchHit] = []
        for result in soup.select(".result"):
            link = result.select_one("a.result__a")
            if link is None:
                continue
            href = (link.get("href") or "").strip()
            if not href:
                continue
            parsed = urlparse(href)
            if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
                href = parse_qs(parsed.query).get("uddg", [href])[0]
            snippet_element = result.select_one(".result__snippet")
            results.append(
                SearchHit(
                    title=_collapse_whitespace(link.get_text(" ", strip=True)),
                    url=href,
                    snippet=_collapse_whitespace(snippet_element.get_text(" ", strip=True)) if snippet_element else "",
                    provider="duckduckgo",
                )
            )
            if len(results) >= 8:
                break
        return results

    async def _google_cse_search(self, query: str) -> list[SearchHit]:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            response = await client.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self._google_api_key,
                    "cx": self._google_cx,
                    "q": query,
                    "num": max(self._settings.web_results_per_target, 3),
                },
                headers={"User-Agent": self._user_agent},
            )
            if response.status_code >= 400:
                return []
            payload = response.json()

        results: list[SearchHit] = []
        for item in payload.get("items") or []:
            url = item.get("link")
            if not url:
                continue
            results.append(
                SearchHit(
                    title=_collapse_whitespace(item.get("title") or ""),
                    url=url,
                    snippet=_collapse_whitespace(item.get("snippet") or ""),
                    provider="google_cse",
                )
            )
        return results

    async def _fetch_page_digest(self, url: str) -> dict[str, Any] | None:
        headers = {"User-Agent": self._user_agent}
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0, connect=10.0),
        ) as client:
            response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                return None
            content_type = response.headers.get("content-type", "")
            text = response.text

        if "html" in content_type:
            soup = BeautifulSoup(text, "html.parser")
            title_text = _collapse_whitespace(soup.title.get_text(" ", strip=True)) if soup.title else ""
            if title_text.lower().startswith("redirecting"):
                meta_refresh = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
                if meta_refresh and meta_refresh.get("content"):
                    content = str(meta_refresh["content"])
                    match = re.search(r"url=(.+)$", content, flags=re.I)
                    if match:
                        redirect_url = match.group(1).strip().strip("'\"")
                        if redirect_url and redirect_url != url:
                            return await self._fetch_page_digest(redirect_url)
            for element in soup(["script", "style", "noscript", "svg"]):
                element.decompose()
            body_text = _collapse_whitespace(soup.get_text(" ", strip=True))
            title = title_text or url
        else:
            body_text = _collapse_whitespace(text)
            title = url

        if not body_text:
            return None
        return {
            "title": title,
            "summary": _summarize_text(body_text, 280),
            "snippet": _truncate(body_text, 340),
            "content_length": len(body_text),
        }

    def _decode_readme(self, payload: dict[str, Any]) -> str:
        encoded = payload.get("content")
        if not encoded:
            return ""
        decoded = base64.b64decode(encoded)
        try:
            return decoded.decode("utf-8")
        except UnicodeDecodeError:
            return decoded.decode("utf-8", errors="ignore")

    def _days_since_timestamp(self, timestamp: str | None) -> int:
        if not timestamp:
            return 999
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            return 999
        return max((datetime.now(timezone.utc) - parsed).days, 0)

    def _infer_target_name_from_scope(self, scope: ResearchScope | None) -> str:
        if not scope or len(scope.comparison_targets) != 1:
            return ""
        return scope.comparison_targets[0].name

    async def _import_source_from_url(self, url: str, *, target_name: str, note: str | None) -> SourceDocument | None:
        digest = await self._fetch_page_digest(url)
        if not digest:
            return None
        domain = _domain_from_url(url)
        lower_domain = domain.lower()
        if "scholar.google" in lower_domain or "cnki" in lower_domain:
            quality = 0.82
            evidence_bucket = "academic_validation"
        else:
            quality = 0.72
            evidence_bucket = "external_validation"
        return SourceDocument(
            run_id="",
            title=digest["title"] or url,
            url=url,
            domain=domain,
            source_type=SourceType.MANUAL_IMPORT,
            summary=digest["summary"],
            snippet=digest["snippet"],
            quality_score=quality,
            tags=[tag for tag in [target_name, "manual-import"] if tag],
            metadata={
                "target_name": target_name,
                "target_rank": 50,
                "search_provider": "manual_url",
                "query": url,
                "note": note,
                "evidence_bucket": evidence_bucket,
            },
        )

    async def _import_source_from_doi(self, doi: str, *, target_name: str, note: str | None) -> SourceDocument | None:
        normalized = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip()
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(20.0, connect=10.0)) as client:
            response = await client.get(
                f"https://api.crossref.org/works/{normalized}",
                params={"mailto": "research-agent@example.com"},
                headers={"User-Agent": self._user_agent},
            )
            if response.status_code >= 400:
                return None
            payload = response.json()
        item = (payload.get("message") or {})
        return self._manual_source_from_crossref_item(item, target_name=target_name, note=note, query=normalized)

    async def _import_source_from_title(self, title: str, *, target_name: str, note: str | None) -> SourceDocument | None:
        params = {
            "query.bibliographic": title,
            "rows": 1,
            "mailto": "research-agent@example.com",
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=httpx.Timeout(20.0, connect=10.0)) as client:
            response = await client.get("https://api.crossref.org/works", params=params, headers={"User-Agent": self._user_agent})
            if response.status_code >= 400:
                return None
            payload = response.json()
        items = (payload.get("message") or {}).get("items") or []
        if not items:
            return None
        return self._manual_source_from_crossref_item(items[0], target_name=target_name, note=note, query=title)

    async def _import_source_from_bibtex(self, bibtex: str, *, target_name: str, note: str | None) -> SourceDocument | None:
        fields = {match.group(1).strip().lower(): _collapse_whitespace(match.group(2)) for match in re.finditer(r"(\w+)\s*=\s*[{\"]([^}\"]+)", bibtex)}
        doi = fields.get("doi")
        url = fields.get("url")
        title = fields.get("title")
        if doi:
            source = await self._import_source_from_doi(doi, target_name=target_name, note=note)
            if source:
                return source.model_copy(update={"metadata": {**source.metadata, "search_provider": "manual_bibtex"}})
        if url:
            source = await self._import_source_from_url(url, target_name=target_name, note=note)
            if source:
                return source.model_copy(update={"metadata": {**source.metadata, "search_provider": "manual_bibtex"}})
        if title:
            source = await self._import_source_from_title(title, target_name=target_name, note=note)
            if source:
                return source.model_copy(update={"metadata": {**source.metadata, "search_provider": "manual_bibtex"}})
        return None

    def _manual_source_from_crossref_item(
        self,
        item: dict[str, Any],
        *,
        target_name: str,
        note: str | None,
        query: str,
    ) -> SourceDocument | None:
        title = _collapse_whitespace(" ".join(item.get("title") or []))
        doi = item.get("DOI")
        url = f"https://doi.org/{doi}" if doi else item.get("URL")
        if not title or not url:
            return None
        abstract = _collapse_whitespace(self._strip_jats(item.get("abstract") or ""))
        venue = _collapse_whitespace(" ".join(item.get("container-title") or []))
        year_parts = ((item.get("issued") or {}).get("date-parts") or [[None]])[0]
        year = year_parts[0] if year_parts else None
        return SourceDocument(
            run_id="",
            title=title,
            url=url,
            domain=_domain_from_url(url),
            source_type=SourceType.MANUAL_IMPORT,
            summary=_summarize_text(abstract or title, 260),
            snippet=_truncate(abstract or f"{title} {venue} {year or ''}", 320),
            quality_score=0.8,
            tags=[tag for tag in [target_name, "manual-import", "academic"] if tag],
            metadata={
                "target_name": target_name,
                "target_rank": 50,
                "search_provider": "manual_doi" if doi else "manual_title",
                "query": query,
                "venue": venue,
                "year": year,
                "doi": doi,
                "note": note,
                "evidence_bucket": "academic_validation",
            },
        )

    def _merge_sources(self, existing: SourceDocument, incoming: SourceDocument) -> SourceDocument:
        existing_tags = list(dict.fromkeys([*existing.tags, *incoming.tags]))
        existing_metadata = {**existing.metadata}
        for key, value in incoming.metadata.items():
            if key not in existing_metadata or existing_metadata[key] in (None, "", [], {}):
                existing_metadata[key] = value
        if existing.quality_score >= incoming.quality_score:
            return existing.model_copy(update={"tags": existing_tags, "metadata": existing_metadata})
        return incoming.model_copy(update={"tags": existing_tags, "metadata": existing_metadata})

    async def _capture(self, awaitable, fallback):
        try:
            return await awaitable
        except Exception:
            return fallback

    def _strip_jats(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"<[^>]+>", " ", text)
