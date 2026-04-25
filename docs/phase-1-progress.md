# Korean Legal Retrieval Engine — Phase 1 Progress

> **Status**: Data Source Layer 조사 단계 (Phase 0 진행 중) **Generated**: 다음 세션 recall용 합의 산출물 **Next session task**: 성문규범 ERD 작성 → Document Parsing Pipeline

---

## 신뢰도 마커 범례

- ✅ **확정**: 실측·문서로 검증됨
- 🔶 **합의**: 실측 전 합의된 결정
- ⚠️ **가설**: 확증 없는 추정 (다음 세션에서 검증 필요)
- ❓ **미해결**: 답이 필요한 결정

---

## 1. 프로젝트 정체성

**한 줄 정의** ✅

> 법제처 API 데이터와 법제처 API 외부의 중대재해처벌법 관련 자료(해설서·공단 매뉴얼·학술자료)를 통합하고, 메타데이터를 풍부화하여 단일 검색 인터페이스로 제공하는 **Retrieval Engine 프로토타입**. 하이브리드 검색·Query Rewriting·Reranker 파이프라인의 효과를 정량 평가(Recall@K, MRR)로 실증.

**범위 결정** ✅

- ✅ Retrieval Engine만 (RAG의 R-layer). Generation은 범위 밖.
- ✅ 도메인: 한국 법률, Phase 1은 **중대재해처벌법**으로 좁힘.
- ✅ 목표: 엔진 성숙 + 포트폴리오 (KTB 2027 H1).

---

## 2. Legal Data 카테고리 정의

| name | description                                  |
| ---- | -------------------------------------------- |
| 성문규범 | 국가 권력이 제정·공포한 법적 구속력을 가진 규범 텍스트              |
| 사법판단 | 법원 또는 헌법재판소가 구체 사건에 대해 내린 판단 기록              |
| 유권해석 | 행정기관이 법령의 의미와 적용에 대해 공식적으로 제시한 해석이나 준사법적 판단  |
| 실무자료 | 법 실무 수행을 돕기 위해 정부와 공공기관이 발행한 법적 효력이 없는 참고 자료 |
| 학술자료 | 학자 또는 법조 실무자가 법령 또는 판례를 해석·체계화·비평한 저작물       |

**카테고리에서 흡수·통합된 것** ✅

- 입법개정자료 → 별도 카테고리에서 제외 (Phase 2+에서 검토)
- 부속참고 → 성문규범 내부의 "별표·서식" 하위 요소로 흡수
- 행정심판 재결 → 사법판단이 아닌 **유권해석**으로 (행정절차이므로)
- 부처 해설서 → 유권해석 vs 실무자료 논쟁 → **실무자료**로 (포맷·용도 기준)
- 대법원판례해설 → 학술자료 (내용 성격 기준)

---

## 3. Phase 1 데이터 범위

|type|name|source|format|
|---|---|---|---|
|성문규범|성문규범|법제처API|XML|
|사법판단|사법판단|법제처API|XML|
|유권해석|유권해석|법제처API|XML|
|학술자료|KLRI|홈페이지|PDF|
|실무자료|해설서|각부처 홈페이지|PDF|
|실무자료|공단매뉴얼|산하 전문기관|PDF|
|실무자료|법령용어사전|법제처API|XML|

**Phase 1 구체 범위** 🔶

성문규범:

- ✅ 중대재해처벌법 (법률, 현행)
- ✅ 중대재해처벌법 시행령 (대통령령, 현행)
- 🔶 형법 중 해설서에 참조된 조항 (선별, DA #5 반영)
- 🔶 고용노동부 고시 (중대재해 관련, 있다면)
- ✅ 시행령 별표 (성문규범 내부 요소)

사법판단:

- 🔶 API로 접근 가능한 판례만 (실측 후 확정)
- ⚠️ 예상 건수: 20~30건 (DA #2에서 실측 필요로 합의)

유권해석:

- 🔶 국가법령정보센터 해석례 API로 접근 가능한 것
- ⏸️ 고용노동부 질의회시 별도 수집은 Phase 2

실무자료:

- ✅ 고용노동부 중대재해처벌법 해설서 (2021.11, 공공누리 1유형)
- ✅ 고용노동부 중대재해처벌법령 FAQ
- 🔶 한국산업안전보건공단 안전보건관리체계 가이드북 (라이선스 재확인)

학술자료:

- 🔶 KLRI 자료 (공공누리 4유형 — 변경금지 제약)
- 🔶 Seheon이 직접 제공하는 PDF 1~3개 (텍스트로 변환 후)

**제외 (Phase 2+로 미룸)**:

- 산업안전보건법 (관련성 높지만 범위 확장)
- 행정규칙·재결례 (Phase 3+)
- 입법개정자료 (제안이유서·회의록·심사보고서 모두)
- 검찰 수사 지침 (접근성 불확실)
- 환경부·국토부 해설서 (Phase 2)
- 로펌 뉴스레터 (저작권)
- 언론 법률 기사 (저작권)

---

## 4. 라이선스 매트릭스

|자료|라이선스|본문 인덱싱|메타만|상업화|
|---|---|---|---|---|
|법제처 API 데이터 (법령·판례·해석례)|공공 (자유 이용 추정) ⚠️|✅|-|🔶|
|고용노동부 중대재해처벌법 해설서|공공누리 1유형 ✅|✅|-|✅|
|고용노동부 FAQ|공공누리 추정 1유형 🔶|✅|-|✅|
|한국산업안전보건공단 가이드북|미확인 ❓|🔶|-|❓|
|KLRI 연구보고서·학술지|공공누리 4유형 ✅|⚠️|✅|❌|
|환경부·국토부 해설서|미확인 ❓|❓|❓|❓|
|산재예방표준용어 CSV|공공데이터 (공단)|❌ (도메인 부적합)|-|-|
|학술 논문 (RISS·KCI)|저자 저작권|❌|🔶 (서지·초록만)|❌|
|로펌 뉴스레터|로펌 저작권|❌|🔶 (메타만)|❌|
|언론 기사|언론 저작권|❌|❌|❌|

**중요 합의 — 공공누리 4유형의 RAG 처리** 🔶

"검색 엔진의 청킹·임베딩이 데이터 가공인가" 문제:

- ✅ Retrieval-only는 4유형과 양립 가능 (회색지대지만 인용 범주)
- ❌ RAG의 Generation 단계는 4유형과 충돌 (LLM이 2차 저작물 생성)
- 🔶 KLRI 자료는 Phase 1에서 본문 인덱싱 가능하되, Phase 4+ Generation 추가 시 제외 필요
- ✅ 라이선스를 청크 메타로 관리: `license_type`, `allowed_uses` 필드

**산재예방표준용어 CSV 검증 결과** ✅

- 19,466개 행이지만 IT 시스템 DB 컬럼 사전 (정의·설명 없음)
- "용어 + 정의" 쌍이 아니라 "컬럼명 + 데이터타입"
- Phase 1 Retrieval에 부적합
- 교훈: 공공데이터포털 자료는 파일명만으로 판단 금지, 샘플 확인 필수

---

## 5. 합의된 설계 결정

### 기술 스택 🔶

1. **언어**: Python + FastAPI + Pydantic
2. **DB**: PostgreSQL + pgvector (Phase 1 규모에 적합, 5M 벡터 미만)
3. **BM25**: bm25s 라이브러리
4. **임베딩**: KURE 또는 bge-m3 (한국어 검색 특화)
5. **Reranker**: bge-reranker-v2-m3 (Phase 3+)
6. **선택**: LangChain·LlamaIndex 사용 안 함 — 직접 구현 (학습·포트폴리오 가치)

### 검색 파이프라인 (Layer 5, Phase 2~4) 🔶

```
사용자 쿼리
    ↓
Query Rewriting (LLM, 원본 + 확장 N개)
    ↓
[원본 + 확장]을 각각 BM25 + Vector 검색
    ↓
RRF Fusion (원본 쿼리에 2x 가중치 — QMD식)
    ↓
Reranker (cross-encoder)
    ↓
Top-K
```

**중요 교정 사항** ✅

- QMD의 RRF는 **원본 쿼리(첫 번째)에 2x 가중치**, hyde 등 특정 타입에 가중치 아님
- Seheon이 README 도식 + CHANGELOG로 검증해서 Claude 오해 교정함
- 인용: "the user's actual words are a more reliable signal"

### 카테고리별 Source Structure 설계 🔶

이 합의가 Phase 1 ERD의 토대:

```
법령 ERD:
  legal_documents + structure_nodes (조·항·호 트리)

판례 ERD:
  case_laws + case_sections (사건번호·판시사항·이유)

유권해석 ERD:
  interpretations + interpretation_sections (질의·회신·이유)

실무·학술 ERD:
  commentaries + commentary_sections (단순 메타 + 장·절)
```

**자료 유형별 ERD 분리 + 검색 인덱스 통합** 🔶

- 자료별 ERD는 각자의 고유 구조 보존 (Seheon 직관 맞음)
- 검색용 `chunks` 테이블은 모든 자료가 통일된 형식으로 들어가는 별도 레이어
- 두 레이어는 외래키로 연결
- "원본은 따로, 검색만 통일" — 이전 혼선 해결

### 13개 설계 원칙 🔶

이전 대화에서 합의된 원칙들:

1. Interface-First (Protocol 사용)
2. Pluggable Components
3. Everything Measurable (explain mode, score traces)
4. Temporal-Ready but Not Temporal-Active
5. Multi-Source by Design (source_type from day one)
6. Collection as First-Class
7. Filters Not Afterthoughts
8. Indexing ⊥ Retrieval
9. Idempotent Indexing
10. Explicit Over Implicit
11. **Query Understanding is First-Class** (Phase 2로 앞당김)
12. **Authority-Aware Retrieval** (authority_level + judgment_status)
13. **Measure First Plan Second** (실측 전 가정 금지)

### 청크 메타데이터 스키마 (구상) 🔶

```
chunks (
  chunk_id,
  source_type,                  -- statute | judicial | interpretive | practical | academic
  source_doc_id,
  source_node_id,               -- 자료별 ERD 외래키
  text,
  context_prefix,
  embedding VECTOR(1024),
  
  -- 권위·시점
  authority_level,
  published_at,
  effective_at,
  superseded_at,
  
  -- 자료 유형별
  court_level,                  -- judicial일 때
  judgment_status,              -- judicial일 때 (다툼/확립/위헌제청)
  interpretation_type,          -- interpretive일 때
  
  -- 라이선스
  license_type,                 -- public | kogl_type1 | kogl_type4 | etc
  allowed_uses,                 -- ['retrieval', 'generation_context', 'redistribution']
  
  -- 출처
  producer,                     -- 고용노동부, 대법원, 공단 등
  metadata JSONB
)
```

### Phase 로드맵 🔶

- **Phase 1 (Walking Skeleton)**: 단일 법령 + 시행령 + 해설서, BM25만, Query Rewriting 없음
- **Phase 2**: Query Rewriting 추가, Vector + RRF
- **Phase 3**: Reranker 추가, 평가 셋 정량화
- **Phase 4**: 그래프 (cross-reference), 시점성 활성화

---

## 6. 미해결 결정 ❓

다음 세션에서 답해야 할 것:

❓ **D-1**: 성문규범 ERD 범위

- A) 최소: 법률 + 시행령 + 시행규칙
- B) 중간: A + 별표·서식
- C) 넓음: B + 행정규칙 (고시·훈령)
- D) 전체: C + 자치법규
- (다음 세션 시작점)

❓ **D-2**: 산하기관 매뉴얼 (공단 가이드북) 라이선스 — 공공누리 어느 유형?

❓ **D-3**: 환경부·국토부 해설서 라이선스 — 공공누리 어느 유형?

❓ **D-4**: 법제처 OpenAPI에 용어 매핑 엔드포인트가 실제로 있는지 — MCP가 별도 구축한 것인지 실측 필요

❓ **D-5**: Document Parsing Pipeline 시작 시점 — ERD 완성 직후? 아니면 ERD + 다른 카테고리 ERD까지 먼저?

❓ **D-6**: KLRI 자료를 Phase 1 본문 인덱싱에 포함할지 (4유형 회색지대 수용 여부)

❓ **D-7**: 학술자료 — Seheon 수동 제공 PDF의 텍스트 변환은 누가? (이전 합의: Seheon이 변환 후 제공)

---

## 7. Phase 0 To-Do List

이전 세션에서 합의된 작업 목록 (✅ 완료, 🔶 진행 중, ⏸️ 대기):

### IP 제한 풀린 후 즉시 실행

⏸️ **T1**: 국가법령정보센터 OpenAPI 회원가입 + 인증키 발급 (Seheon 보유)

⏸️ **T2**: API 엔드포인트 카탈로그 정리

- `target=law/prec/expc/admrul/ordin` 등 17개 도메인
- 각 응답 포맷·파라미터 문서화
- → `docs/data-sources/law-go-kr-api-catalog.md`

⏸️ **T3-A**: 중대재해처벌법 본문 가져오기 (curl/Python requests)

- 시행령·시행규칙 동반 확인
- → `data/raw/중대재해처벌법/`

⏸️ **T4-A**: 응답 구조 분석

- 조·항·호 XML 구조
- 위임조문 메타데이터 분리 여부
- 시행일·개정이력 필드
- → `docs/data-sources/중대재해처벌법-schema.md`

⏸️ **T5-A**: 시행령·시행규칙 연결 메타 확인

⏸️ **T6-B**: 중대재해처벌법 판례 API 실측 (강화)

- 대법원·고등·지방별 건수
- 전문 조회 가능 건수
- → `docs/data-sources/판례-접근성-실측.md`

⏸️ **T7-A 확장**: 참고자료 인벤토리

- 고용노동부 공개자료실
- 한국산업안전보건공단 자료실
- 환경부·국토부
- 각 자료의 URL + 라이선스 표시 기록

⏸️ **T8**: 행정규칙·유권해석 API 존재 확인 (Phase 2+ 후보 기록)

⏸️ **T9**: 라이선스 약관 체크

- 법제처 API 이용약관
- 데이터 재배포·상업 이용·저작권 표시 의무
- → `docs/data-sources/license-compliance.md`

⏸️ **T10-A**: Phase 1 데이터 범위 문서화

- → `docs/phase-1-scope.md`

⏸️ **T11-A**: Phase 1 raw 데이터 덤프

⏸️ **T15**: 형법 참조 조항 인벤토리

- 고용노동부 해설서에서 인용된 형법 조항 추출
- 30~50개 조항 목록화
- → `docs/data-sources/referenced-criminal-law-articles.md`

⏸️ **T16**: 라이선스별 자료 분류표 작성

⏸️ **T17**: 저작권 엄격 자료의 메타 수집 방식 결정

⏸️ **T18**: 법제처 용어 API 실측

- `get_legal_term_kb`, `get_daily_to_legal`, `get_legal_to_daily` 실제 호출
- 데이터 출처가 법제처 OpenAPI인지 확정

⏸️ **T19**: 공단 안전보건 용어집 조사 (산재예방표준용어 CSV는 부적합으로 확정됨)

### 선택 작업

⏸️ **T12**: 국가법령정보센터 자연어 검색 직접 체험 ⏸️ **T13**: LBox Open 데이터 포맷 훑어보기 ⏸️ **T14**: 국회 의안정보시스템 제안이유서 접근 확인 (Phase 2+)

---

## 8. Devil's Advocation 기록

이 프로젝트의 **자기 검증 라운드**들. 각각이 설계 결정에 영향.

### DA #1 — 7개 분류가 맞는가?

**공격**: 분류축이 일관 안 됨, 카테고리 판단 비용 높음 **결과**: ✅ 7개 → 5개로 축소 (Seheon 최종 정리에 반영)

### DA #2 — 부속참고는 성문규범의 일부 아닌가?

**공격** (Seheon 제기): 별표는 법령 본문과 함께 공포됨, 같은 효력 **결과**: ✅ 부속참고 카테고리 해체. 별표는 성문규범 하위 요소로

### DA #3 — 사법판단 단일 카테고리가 너무 이질적

**공격**: 대법원·고등·지법·헌재의 권위가 너무 다름 **결과**: 🔶 카테고리 분할이 아니라 메타데이터 (court_level, judgment_status)로 해결

### DA #4 — 한국 법체계 특화 = 확장성 약함

**공격**: 다국가 확장 어려움 **결과**: ✅ 인정하되 현재 대응 불필요. "한국 특화"로 명시적 포지셔닝

### DA #5 — 검색 관점에서 7개가 의미 있는가?

**공격**: 카테고리는 적게, 메타데이터로 세분화가 더 실용적 **결과**: ✅ 5개 카테고리 + 풍부한 메타데이터로 합의

### DA #6 — 모든 자료를 분류에 가두는 전제 위험

**공격**: 경계 자료가 항상 발생, 완벽 분류 불가능 **결과**: ✅ 100% 커버리지 목표 포기. 진화하는 분류로 인정

### DA #7 — 16개 조문이 통계적 해상도 부족

**공격**: ablation study 불가능 **결과**: ✅ Phase 1은 Walking Skeleton 목적, ablation은 Phase 2+로

### DA #8 — 판례 35건 가정이 미검증

**공격**: API 접근성 실측 안 됨 **결과**: ✅ T6-B로 실측 작업 강화

### DA #9 — 법 자체가 불안정 (위헌제청 + 판례 미확립)

**공격**: 검색 결과가 오정보가 될 수 있음 **결과**: ✅ judgment_status 메타로 다툼/확립/위헌제청 표시

### DA #10 — 해설서 품질·시점 기복

**공격**: 해설서가 판례 변화 미반영 **결과**: ✅ authority_level + published_at 메타로 권위·시점 표시

### DA #11 — 형법 본문 인덱싱 누락

**공격**: 중대재해처벌법은 형법 특별법, 형법 본문 없으면 실무 가치 절반 **결과**: ✅ 해설서가 인용한 형법 조항만 선별 인덱싱

### DA #12 (Seheon 제기) — 자연어 쿼리 자기모순

**공격**: MCP에 자연어 라우팅이 있는데 "자연어 약함"이라고 한 건 모순 **결과**: ✅ Claude 자기모순 인정. 벡터 검색의 가치를 "조건부"로 재평가

### DA #13 (Seheon 제기) — RRF가 정말 필요한가

**공격**: 법제처가 이미 자기 데이터 잘 안다고 가정하면 RRF 효과 미증명 **결과**: ✅ 가설로 격하. Phase 1에 비교 측정(법제처 vs Seheon 엔진) 명시 추가

---

## 9. Claude의 미끄러짐 기록 (다음 세션 경고)

**다음 세션의 Claude에게**: 이 프로젝트에서 반복적으로 발생한 실수 패턴. 같은 패턴 재발생 시 Seheon이 즉시 멈춰세울 것.

### 미끄러짐 #1: 용어 임의 생성

**사건**: "3-Layer Storage Pattern"이라는 표현을 업계 표준처럼 제시 **진실**: 업계 표준 용어 아님. RAGFlow의 "Load vs Indexing"이 가장 가까운 정식 명칭 **Seheon 교정**: 검증 요청으로 발견 **경계**: 새 용어 사용 시 반드시 출처 확인. 임의 명명 금지.

### 미끄러짐 #2: 문서 조각 과잉 해석

**사건**: QMD의 "first query gets 2x weight"를 "hyde에 2x"라고 단정 **진실**: README 도식과 CHANGELOG 인용 모두 "원본 쿼리에 2x" **Seheon 교정**: 실제 README 도식 첨부로 발견 **경계**: 문서 조각 해석 시 합성 추론 금지. 원문 확인 우선.

### 미끄러짐 #3: 양방향 매핑 단정

**사건**: MCP가 일상어↔법률용어 매핑 도구 제공 → "법제처가 공식 제공"으로 확장 **진실**: MCP 도구 존재만 확증, 데이터 출처 불명 (법제처 API 직접인지 별도 구축인지) **Seheon 교정**: "정말 그래?" 의심 질문으로 발견 **경계**: 도구·기능 존재를 데이터 출처로 자동 확장 금지.

### 미끄러짐 #4: 레이어 침범

**사건**: Data Source Layer 단계에서 ERD·청크 테이블·검색 인덱스 설계로 미끄러짐 **Seheon 교정**: "야! 이러니까 헷갈리지!!! 내가 Data Source Layer부터 하자고 했잖아!!!" **경계**: Seheon이 명시한 레이어 밖으로 이동 금지. 다른 레이어를 **고려**하는 것과 **집중**하는 것을 구분.

### 미끄러짐 #5: 가정을 사실처럼

**사건**: "판례 35건 확보 가능" 같은 미검증 숫자를 가정으로 사용 **Seheon 교정**: DA #8에서 실측 요구 **경계**: "예상", "추정" 표시 없이 숫자 제시 금지.

### 미끄러짐 #6: MCP 능력 과소평가

**사건**: "MCP는 자연어 쿼리에 약함"이라고 단언 **진실**: MCP는 LLM 라우팅으로 자연어 처리. Vector 검색이 없을 뿐. **Seheon 교정**: "자연어 자동 라우팅이 있는데 자연어 못한다고?" 모순 지적 **경계**: 경쟁 제품 능력 평가 시 동시에 가진 다른 능력도 함께 고려.

### 공통 패턴

이 6개 미끄러짐의 공통 구조:

1. 일부 정보(증거 조각)를 받는다
2. **확장 추론**으로 의미를 부풀린다
3. **확정처럼** 제시한다
4. Seheon이 검증 요청 또는 모순 지적
5. Claude가 정정

**예방 행동**:

- 새 정보 제시 전: "이건 확정인가, 추론인가?" 자문
- 수치·표준·공식 사실 인용 시: 출처 명시
- 경쟁 제품 평가 시: 양면 (장점·약점) 동시 검토
- Seheon이 명시한 범위 밖으로 갈 때: 명시적 허락 받기

---

## 10. 다음 세션 시작 가이드

**즉시 할 것**:

1. 이 문서를 다음 세션 시작 시 첨부
2. Seheon이 정리한 **5개 카테고리 + 7개 데이터 소스 표** 재확인
3. **D-1** (성문규범 ERD 범위) 결정부터
4. 합의된 카테고리별 Source Structure 설계 (5번 섹션)에서 **법령 ERD** 부분을 출발점으로

**ERD 작성 시 고려할 다른 레이어 사항** (이전 합의):

- **Document Parsing Pipeline 관점**:
    
    - 법제처 API XML 응답 → ERD 매핑 가능성
    - 위임조문 ("대통령령으로 정하는") 처리
    - 형법 참조 조항 처리
    - 시행령 별표 (HWP/HWPX)
- **Indexing Layer 관점**:
    
    - chunks 테이블이 역참조할 안정적 node_id
    - 법령 개정 시 node_id 유지 또는 버전 관리
- **Retrieval Pipeline 관점**:
    
    - 조문 + 별표 + 위임 시행령 조문을 함께 반환할 수 있는 관계 구조
- **시점성 관점**:
    
    - Phase 1은 현행만, 스키마는 이력 수용 가능하게
    - effective_at, superseded_at 필드 미리 준비

**ERD 작업 후 자연스럽게 이어질 것**:

- Document Parsing Pipeline 설계
- 다른 카테고리 ERD (사법판단·유권해석 등)
- 라이선스 메타 필드 통합

---

## 11. 핵심 참고 자원

### 외부 자원

- **법제처 OpenAPI**: `https://www.law.go.kr/DRF/`
    - `lawSearch.do` (검색), `lawService.do` (조회)
    - `target` 파라미터로 도메인 분기
    - 기본 응답: XML, 일부 JSON 지원
- **공공데이터포털**: `data.go.kr` (파일 데이터 형식)
- **고용노동부 자료실**: `moel.go.kr/policy/policydata`
- **한국법제연구원 (KLRI)**: `klri.re.kr`
- **MCP 참고 (개발자 공개)**: `chrisryugj/korean-law-mcp`
    - 89개 도구, 14개 노출
    - 법제처 API 래퍼로 작동
    - 자체 검색 인덱스 없음

### 기술 참조

- **QMD** (`tobi/qmd`): 검색 파이프라인 레퍼런스
    - 원본 쿼리 + 2개 확장 쿼리 → BM25/Vector 병렬 → RRF (원본 2x) → Reranker
- **Hybrid RAG** (2025 엔터프라이즈 표준): Vector + Graph + Structured
- **RAGFlow**: Load vs Indexing 분리 프레이밍
- **maastrichtlawtech/fusion**: 프랑스 법률 하이브리드 검색 레퍼런스
- **LBox Open**: 한국 판례 데이터셋 (CC BY-NC, 147k 판례)
- **KURE / bge-m3**: 한국어 검색 임베딩

---

## 12. 변경 이력 (이 문서)

- v1.0: 초기 산출물 작성 (합의 사항 압축)
- (다음 세션에서 ERD 추가, 신뢰도 마커 갱신, 새 결정사항 추가)
