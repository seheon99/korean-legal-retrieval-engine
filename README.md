# Korean Legal Retrieval Engine

Production-grade retrieval engine (R-layer of RAG) for Korean statutory
data. Phase 1 walking skeleton built around 중대재해처벌법 (Serious
Accidents Punishment Act, 2021).

The codebase prioritizes correctness, measurement, and idiomatic Postgres
over orchestrator frameworks. No LangChain, no LlamaIndex.

## Status

Phase 1 — ingestion-pipeline / query-layer design. Phase-1 statute
schema frozen as `migrations/001_statute_tables.sql` per ADR-010.

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

### Raw API responses are local-only

Two local-only directories hold 법제처 API responses, both gitignored:

- `data/raw/{law_id}/{mst}.xml` — canonical retention store for full
  document responses (`lawService.do`) per
  [ADR-011](docs/decisions/ADR-011-raw-api-xml-retention.md).
  Indefinite retention; integrity link via `legal_documents.content_hash`.
- `docs/api-samples/` — developer-facing samples for ADR drafting and
  ad-hoc inspection. Search responses (`lawSearch.do`) write here.

Responses contain the OC parameter echoed inside `법령상세링크` URLs,
so they're kept out of git rather than scrubbed on every fetch.

To populate both stores on a fresh clone:

1. Register an OC at <https://www.law.go.kr/LSO/openApi/cuAskList.do> and
   whitelist your egress IP. (Cafe / public Wi-Fi will not work — the
   request is rejected at the IP check.)
2. Export the OC into your shell environment, e.g. `export LAW_GO_KR_OC=...`.
3. Run the fetch script:

```bash
./scripts/fetch_law_samples.sh                  # Phase-1 default set
./scripts/fetch_law_samples.sh --force          # overwrite existing
./scripts/fetch_law_samples.sh --doc 013993 228817   # single document
./scripts/fetch_law_samples.sh --search 중대재해      # single search
./scripts/fetch_law_samples.sh --help
```

The script is idempotent (skips files that exist unless `--force`) and
writes atomically (tmp + rename) to avoid half-written files on crash.

Path conventions:

- Documents: `data/raw/{law_id}/{mst}.xml` (e.g.
  `data/raw/013993/228817.xml` for the Act).
- Searches: `docs/api-samples/search-{query}.xml` (e.g.
  `docs/api-samples/search-중대재해.xml`).

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
├── migrations/              ← DDL versioned from day 1 (001_statute_tables.sql per ADR-010)
├── data/
│   └── raw/                 ← retention store per ADR-011 (gitignored)
├── src/                     ← Python source
├── scripts/                 ← fetchers, one-off utilities
│   └── fetch_law_samples.sh ← API fetch utility
└── tests/
```

See `CLAUDE.md` §7 for the canonical layout description.
