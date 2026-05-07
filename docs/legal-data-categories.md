# Legal Data Categories and Phase-1 Sources

Durable taxonomy for KLRE source materials and the Phase-1 source inventory.
This document is the canonical place for category definitions; phase plans
and progress notes link here rather than restating the table.

For SAPA + OSH Phase-1 statutory scope, see
[decisions/ADR-019-phase-1-osh-scope.md](decisions/ADR-019-phase-1-osh-scope.md).

## Five canonical categories

| Name | Description |
| ---- | ---- |
| 성문규범 (Statutes) | Normative texts enacted and promulgated by state authority with legal binding force |
| 사법판단 (Judicial Decisions) | Records of decisions by courts or the Constitutional Court on specific cases |
| 유권해석 (Authoritative Interpretation) | Official interpretations or quasi-judicial decisions by administrative agencies |
| 실무자료 (Practical References) | Reference materials issued by government and public agencies for practical work, without legal force |
| 학술자료 (Academic & Commentary) | Works by scholars or legal practitioners interpreting, systematizing, or critiquing law and case law |

## How the taxonomy was reached

- Initial draft: 7 categories
  (statute / judicial / interpretive / academic / legislative / appendix /
  practical).
- DA #1: classification axes were mixed → reduce.
- DA #2 (raised by owner): appendices are part of the statute itself → tables
  and forms absorbed into 성문규범.
- DA #5: from a search standpoint, fewer categories with richer metadata is
  more practical → settle at 5 categories + rich metadata.
- Final: 5 categories. Legislative materials are deferred to Phase 2+.
  Administrative-appeal rulings sit under 유권해석 (administrative procedure,
  not judicial). Ministry commentaries sit under 실무자료 (form and purpose,
  not authority). Supreme Court case commentaries sit under 학술자료 (content
  nature outweighs publisher).

## Phase-1 source inventory

| Type | Name | Source | Format |
| ---- | ---- | ---- | ---- |
| Statute | 성문규범 | law.go.kr API (`target=eflaw`) | XML |
| Judicial | 사법판단 | law.go.kr API | XML |
| Interpretive | 유권해석 | law.go.kr API | XML |
| Academic | KLRI publications | KLRI website | PDF |
| Practical | Ministry commentaries | Each ministry's website | PDF |
| Practical | Public agency manuals | Affiliated specialized agencies | PDF |
| Practical | Legal terminology | law.go.kr API | XML |

### Phase-1 statutory scope (concrete)

- **SAPA family** (`중대재해 처벌 등에 관한 법률`): Act + Enforcement Decree.
  No 시행규칙 exists for this statute.
- **OSH family** (`산업안전보건법`): Act + 시행령 + 시행규칙.
- Effective-as-of `2026-05-06` is the default retrieval/eval slice;
  head/future rows are explicit-mode only per ADR-013 / ADR-021.
- Selected Criminal Code articles referenced by the official commentary
  remain in scope (DA #11), bounded by ADR-019's corpus rule.
- Annexes are statute sub-elements (ADR-001). Forms are live for OSH 시행규칙
  but persistence-only in Phase 1 (ADR-005).

### Phase-1 non-statutory scope (intent, not yet ingested)

- **Judicial**: only what the API returns (count to be measured).
- **Interpretive**: whatever the law.go.kr interpretation API returns.
  MoEL Q&A as a separate source is deferred to Phase 2.
- **Practical**: MoEL Serious Accidents Punishment Act Commentary
  (Nov 2021, KOGL Type 1); MoEL FAQ; KOSHA Safety and Health Management
  System Guide pending license re-verification.
- **Academic**: KLRI materials (KOGL Type 4 — gray-area for retrieval-only,
  excluded if Generation is added later);
  1–3 owner-supplied PDFs converted to text first.

### Excluded (deferred to Phase 2+)

- Administrative regulations and rulings (Phase 3+).
- Legislative materials (proposal rationale, minutes, review reports).
- Prosecution investigation guidelines (access uncertain).
- MoE / MoLIT commentaries (Phase 2).
- Law firm newsletters; press articles on legal topics (copyright).
