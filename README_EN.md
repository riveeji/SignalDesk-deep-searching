# SignalDesk / 研策台

SignalDesk is an `Agentic Deep Research System` built for `AI / Agent` technology selection.

Instead of answering directly from a single prompt, it decomposes a research task into `clarify -> plan -> retrieve -> synthesize -> validate`, persists the full trajectory, and exports a citation-backed report with explicit evidence coverage and confidence.

## Highlights

- Single search-box entry for complex research questions
- Multi-stage research loop with `Clarifier / Planner / Retriever / Synthesizer / Validator`
- Multi-source evidence collection from `GitHub API`, official docs, web search, `Crossref`, and manual imports
- Full persistence with `PostgreSQL`
- Citation-backed Chinese reports with `Markdown / PDF` export
- Guardrails based on `coverage / verdict / confidence`
- Human-in-the-loop controls: clarify, exclude, import, retry

## Real run snapshots

- `research_22f8fcc3c7`: 3 targets, 15 sources, 35 citations, `164.5s`, `grounded / high`
- `research_6ce72c568b`: 1 target, 3 sources, 7 citations, `133.2s`, `grounded / medium`
- `research_0a1068cdbb`: regression case after source exclusion, downgraded to `insufficient_evidence / low`

## Stack

- `Next.js`
- `FastAPI`
- `PostgreSQL`
- `DeepSeek`

## More

- Chinese README: [README.md](README.md)
- Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Demo script: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md)
- Interview pitch: [docs/INTERVIEW_PITCH.md](docs/INTERVIEW_PITCH.md)
