# Korean Legal Retrieval Engine

Production-grade retrieval engine (R-layer of RAG) for Korean statutory
data. Phase 1 walking skeleton built around 중대재해처벌법 (Serious
Accidents Punishment Act, 2021).

The codebase prioritizes correctness, measurement, and idiomatic Postgres
over orchestrator frameworks. No LangChain, no LlamaIndex.

## Status

Phase 0 — schema design.

- `docs/legal-erd-draft.md` — working ERD draft (statute scope, Phase 1)
- `docs/decisions/` — ADRs, one file per decision
- `docs/sessions/` — session logs, one file per work day
- `docs/phase-1-progress.md` — full Phase 0 synthesis (553 lines)

## Stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.11+ · FastAPI · pydantic |
| Storage | PostgreSQL + pgvector |
| Sparse retrieval | bm25s |
| Embeddings | KURE or bge-m3 (Korean-tuned; choice deferred) |
| Reranker | bge-reranker-v2-m3 (Phase 3+) |

## Data sources

Statute, judicial, and interpretive data are pulled from the 법제처
OpenAPI (`https://www.law.go.kr/DRF/`). Access requires an OC (인증키)
registered with an IP-whitelisted endpoint.

### `docs/api-samples/` is local-only

Raw 법제처 API responses used during schema design live under
`docs/api-samples/`, which is **excluded from version control** via
`.gitignore`. The responses contain the OC parameter inside echoed
`법령상세링크` URLs, so they're easier to keep out of git than to scrub
on every fetch.

To re-create the samples on a fresh clone:

1. Register an OC at <https://www.law.go.kr/LSO/openApi/cuAskList.do> and
   whitelist your egress IP. (Cafe / public Wi-Fi will not work — the
   request is rejected at the IP check.)
2. Export the OC into your shell environment, e.g. `export LAW_GO_KR_OC=...`.
3. Fetch the Phase 1 samples (Act + 시행령 + a search response):

```bash
mkdir -p docs/api-samples
curl -s "https://www.law.go.kr/DRF/lawService.do?OC=$LAW_GO_KR_OC&target=law&MST=228817&type=XML" \
  -o docs/api-samples/law-228817-중대재해처벌법.xml
curl -s "https://www.law.go.kr/DRF/lawService.do?OC=$LAW_GO_KR_OC&target=law&MST=277417&type=XML" \
  -o docs/api-samples/law-277417-중대재해처벌법시행령.xml
curl -s "https://www.law.go.kr/DRF/lawSearch.do?OC=$LAW_GO_KR_OC&target=law&type=XML&display=5&query=%EC%A4%91%EB%8C%80%EC%9E%AC%ED%95%B4" \
  -o docs/api-samples/search-중대재해.xml
```

A proper fetch script will land at `scripts/fetch_law_samples.sh` once
ingestion development begins.

Sample-naming convention: `law-<MST>-<short-title>.xml` for full law
fetches, `search-<keyword>.xml` for search responses.

## Repository layout

```
legal-retrieval/
├── CLAUDE.md                ← AI agent operating manual (loaded each session)
├── README.md                ← this file
├── docs/
│   ├── legal-erd-draft.md   ← current ERD work
│   ├── phase-1-progress.md  ← Phase 0 synthesis
│   ├── decisions/           ← ADR-NNN-<slug>.md
│   ├── sessions/            ← YYYY-MM-DD.md
│   └── api-samples/         ← local-only (gitignored)
├── migrations/              ← DDL versioned from day 1 (empty in Phase 0)
├── src/                     ← Python source (empty in Phase 0)
├── scripts/                 ← fetchers, one-off utilities (empty in Phase 0)
└── tests/                   ← (empty in Phase 0)
```

See `CLAUDE.md` §7 for the canonical layout description.
