from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    vendor: str
    kind: str
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    enabled: bool = False


@dataclass(frozen=True)
class AppSettings:
    database_url: str
    frontend_origins: tuple[str, ...]
    output_language: str
    report_audience: str
    report_style: str
    llm_temperature: float
    llm_timeout_seconds: float
    web_results_per_target: int
    default_provider_id: str
    provider_presets: tuple[ProviderPreset, ...]

    @property
    def default_provider(self) -> ProviderPreset:
        provider = next(
            (item for item in self.provider_presets if item.id == self.default_provider_id and item.enabled),
            None,
        )
        if provider is not None:
            return provider
        return next(item for item in self.provider_presets if item.id == "heuristic")

    @property
    def provider_name(self) -> str:
        return self.default_provider.id

    @property
    def model_label(self) -> str:
        return self.default_provider.model or "heuristic-fallback"


def load_settings() -> AppSettings:
    _load_env_file(Path(__file__).resolve().parents[1] / ".env")
    deepseek_api_key = os.getenv("DEEP_RESEARCH_DEEPSEEK_API_KEY")
    provider_presets = (
        ProviderPreset(
            id="heuristic",
            label="启发式回退",
            vendor="内置",
            kind="heuristic",
            enabled=True,
            model="heuristic-fallback",
        ),
        ProviderPreset(
            id="deepseek",
            label="DeepSeek",
            vendor="DeepSeek",
            kind="openai-compatible",
            base_url=os.getenv("DEEP_RESEARCH_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=deepseek_api_key,
            model=os.getenv("DEEP_RESEARCH_DEEPSEEK_MODEL", "deepseek-chat"),
            enabled=bool(deepseek_api_key),
        ),
    )

    return AppSettings(
        database_url=os.getenv(
            "DEEP_RESEARCH_DATABASE_URL",
            os.getenv("OPSPILOT_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:15432/deepresearch"),
        ),
        frontend_origins=_split_csv(
            os.getenv(
                "DEEP_RESEARCH_FRONTEND_ORIGINS",
                os.getenv("OPSPILOT_FRONTEND_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"),
            )
        ),
        output_language=os.getenv("DEEP_RESEARCH_OUTPUT_LANGUAGE", "简体中文"),
        report_audience=os.getenv("DEEP_RESEARCH_REPORT_AUDIENCE", "需要快速做出技术判断的工程团队"),
        report_style=os.getenv("DEEP_RESEARCH_REPORT_STYLE", "结构化、克制、可追溯、结论明确"),
        llm_temperature=float(os.getenv("DEEP_RESEARCH_LLM_TEMPERATURE", "0.15")),
        llm_timeout_seconds=float(os.getenv("DEEP_RESEARCH_LLM_TIMEOUT_SECONDS", "60")),
        web_results_per_target=int(os.getenv("DEEP_RESEARCH_WEB_RESULTS_PER_TARGET", "2")),
        default_provider_id=os.getenv("DEEP_RESEARCH_DEFAULT_PROVIDER", "deepseek").strip().lower() or "deepseek",
        provider_presets=provider_presets,
    )
