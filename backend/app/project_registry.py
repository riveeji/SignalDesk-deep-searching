from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectDescriptor:
    name: str
    repo_full_name: str
    docs_url: str
    homepage_url: str
    aliases: tuple[str, ...]


KNOWN_PROJECTS: list[ProjectDescriptor] = [
    ProjectDescriptor(
        name="Qwen",
        repo_full_name="",
        docs_url="https://qwenlm.github.io/",
        homepage_url="https://qwenlm.github.io/",
        aliases=("qwen", "tongyi qianwen"),
    ),
    ProjectDescriptor(
        name="DeepSeek",
        repo_full_name="",
        docs_url="https://api-docs.deepseek.com/",
        homepage_url="https://www.deepseek.com/",
        aliases=("deepseek",),
    ),
    ProjectDescriptor(
        name="Kimi",
        repo_full_name="",
        docs_url="https://platform.moonshot.cn/docs/intro",
        homepage_url="https://platform.moonshot.cn/",
        aliases=("kimi", "moonshot", "moonshot ai"),
    ),
    ProjectDescriptor(
        name="LangGraph",
        repo_full_name="langchain-ai/langgraph",
        docs_url="https://docs.langchain.com/oss/python/langgraph/",
        homepage_url="https://www.langchain.com/langgraph",
        aliases=("langgraph",),
    ),
    ProjectDescriptor(
        name="CrewAI",
        repo_full_name="crewAIInc/crewAI",
        docs_url="https://docs.crewai.com/",
        homepage_url="https://www.crewai.com/",
        aliases=("crewai", "crew ai"),
    ),
    ProjectDescriptor(
        name="AutoGen",
        repo_full_name="microsoft/autogen",
        docs_url="https://microsoft.github.io/autogen/stable/",
        homepage_url="https://microsoft.github.io/autogen/",
        aliases=("autogen", "auto gen"),
    ),
    ProjectDescriptor(
        name="Mastra",
        repo_full_name="mastra-ai/mastra",
        docs_url="https://mastra.ai/docs",
        homepage_url="https://mastra.ai/",
        aliases=("mastra",),
    ),
    ProjectDescriptor(
        name="LlamaIndex",
        repo_full_name="run-llama/llama_index",
        docs_url="https://docs.llamaindex.ai/",
        homepage_url="https://www.llamaindex.ai/",
        aliases=("llamaindex", "llama index"),
    ),
    ProjectDescriptor(
        name="Haystack",
        repo_full_name="deepset-ai/haystack",
        docs_url="https://docs.haystack.deepset.ai/",
        homepage_url="https://haystack.deepset.ai/",
        aliases=("haystack",),
    ),
    ProjectDescriptor(
        name="PydanticAI",
        repo_full_name="pydantic/pydantic-ai",
        docs_url="https://ai.pydantic.dev/",
        homepage_url="https://ai.pydantic.dev/",
        aliases=("pydanticai", "pydantic ai"),
    ),
    ProjectDescriptor(
        name="OpenHands",
        repo_full_name="All-Hands-AI/OpenHands",
        docs_url="https://docs.all-hands.dev/",
        homepage_url="https://www.all-hands.dev/",
        aliases=("openhands", "open hands"),
    ),
]


def find_project_by_alias(term: str) -> ProjectDescriptor | None:
    needle = term.strip().lower()
    for project in KNOWN_PROJECTS:
        if needle == project.name.lower() or needle in project.aliases:
            return project
    return None
