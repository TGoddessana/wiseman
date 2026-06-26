# `/summon-wiseman` 설계 문서 (v3 — SQLite+MCP 위의 LLM 위키)

- 작성일: 2026-06-26
- 상태: 설계 확정 대기 (사용자 리뷰)
- 제품명: **Wiseman** — "코딩하기 전에 여쭤보는 현자(wise man)"
- 한 줄 요약: 현재 프로젝트를 분석·심층 조사하여, **그 코드베이스 전용 LLM 위키**(카르파시식 개념)를 **SQLite + MCP** 위에 구축·유지하는 Claude Code 플러그인. 코딩 전에 에이전트가 위키에 "여쭤보고"(`ask_wiseman`), 새로 배운 건 위키에 되먹여(`write_page`) **쓸수록 똑똑해진다.**

> **버전 이력**
> - v1: Context7식 MCP + SQLite (개념 모델 빈약)
> - v2: 순수 마크다운 LLM 위키 (MCP/DB 제거)
> - **v3 (현재): 합본** — substrate는 v1의 **SQLite+MCP**, 개념은 v2의 **LLM 위키**(레이어/복리/ingest·query·lint/schema.md 주입).
>
> **핵심 통찰**: 카르파시 문서는 "의도적으로 추상적" — LLM 위키는 *개념*이지 *구현*이 아니다. 같은 개념(레이어·복리·연산·스키마)을 마크다운에도, SQLite에도 올릴 수 있다. 순수 SQLite 단일소스는 마크다운↔인덱스 **드리프트가 원천적으로 없고**, 임베딩·대시보드·대규모 랭킹 검색이라는 향후 방향에 자연스럽다.
>
> 네이밍 노트: `wiseman`은 확정 제품명. 저장소 디렉토리명 `teachers-mcp`는 가명 — 추후 리네임 가능(코스메틱).

---

## 1. 목적과 핵심 가치 기준 (불변)

Wiseman은 **"우리 코드베이스에 딱 맞는 LLM 위키"** 를 만든다. 코딩 중 Claude가 행동 전에 위키에 "여쭤보면", 그 프로젝트의 실제 스택·버전·관례·함정에 맞는 답을 얻는다.

### 절대적 성공 기준 (Non-negotiable)

> **위키에 물어서 얻은 답은, 모델이 자기 내부 지식만으로 짜는 것보다 반드시 더 나아야 한다.**

따라서 위키의 모든 페이지는 다음을 만족해야 한다:

1. **최신성** — 웹 심층 조사로 현재 버전 기준 정보를 수집
2. **버전 핀(pin)** — 프로젝트에 실제로 설치된 버전에 고정
3. **출처(source) 보유** — 공식 문서 URL / 설치 코드 경로 / `derived-principle` 명시
4. **프로젝트 고유성** — 일반론이 아니라 이 프로젝트의 스택/아키텍처/관례 반영
5. **비자명성** — 뻔한 내용이 아니라 함정·안티패턴·관례 중심

빌드 시 **품질 게이트**(§9)로, 운영 중 **`lint` 연산**(§7-3)으로 강제한다.

---

## 2. 핵심 모델: LLM 위키 개념 ⊕ SQLite+MCP substrate

카르파시의 3계층 / 3연산을 SQLite+MCP로 구현한다.

| 카르파시 개념 | Wiseman 구현 (substrate) |
|----------|--------------|
| ① 원본 소스(불변) | 공식 문서, 설치된 라이브러리 코드, 프로젝트 자체 코드 |
| ② 위키 (LLM 소유) | **SQLite `wiki.db`** — `pages`/`links`/`log` 테이블 (단일 진실 소스) |
| ③ 스키마 (CLAUDE.md식 설정) | **`schema.md`** (CLAUDE.md에 `@import`로 상시 로드) — substrate 무관 |
| 연산: `ingest` | `summon-wiseman`(최초 대량) / 이후 증분 |
| 연산: `query` | `ask_wiseman` 검색 + **유용한 종합을 `write_page`로 되먹임(복리)** |
| 연산: `lint` | SQL 기반 건강 점검 (고아·낡음·모순) |

**왜 SQLite+MCP인가**: 드리프트 0(단일소스), 임베딩 확장 자연스러움(vector 테이블), 컨텍스트 효율(큐레이션 청크만 반환), 복리/lint를 SQL로 깔끔히, 향후 대시보드 연동 용이.

---

## 3. 컨텍스트 사용 모델 (오해 방지)

위키 전체를 컨텍스트에 넣지 **않는다**.

| 무엇 | 컨텍스트에? |
|------|------------|
| `schema.md` (지도+규칙) | **항상 로드** (CLAUDE.md `@import`) — "위키 구조와 ask/write/lint 사용법" |
| `wiki_index()` 결과 (목차) | 필요시 |
| 개별 페이지 / 검색 청크 | **관련된 것만** (`ask_wiseman`/`get_page`) |
| 위키 전체 | **절대 통째로 안 넣음** |

상시 상주는 작은 "사용법 지도"(schema.md)뿐. `ask_wiseman`은 위키 전체를 안 넣고도 **관련 청크만 정확히 반환**하는 선택적 검색기다.

---

## 4. 아키텍처

### 레이어 1 — 플러그인 (배포물, 한 곳에서 관리)

`wiseman` 플러그인이 번들하는 것:

- `summon-wiseman` **스킬** — 분석·조사·위키 빌드 지시문
- **범용 Wiseman MCP 서버** (Python + FastMCP) — `wiki.db`를 읽고 쓰는 도구 제공
- **`schema.md` 템플릿** — 위키 운영 매뉴얼 원본
- (향후) 편집 대시보드, 임베딩 인덱서

플러그인 설치 시 MCP 서버가 **자동 등록**된다. 서버 코드는 `${CLAUDE_PLUGIN_ROOT}`에 한 벌, db 경로는 `${CLAUDE_PROJECT_DIR}`로 현재 프로젝트를 자동 지정:

```jsonc
// 플러그인의 .mcp.json (또는 plugin.json 의 mcpServers)
{
  "mcpServers": {
    "wiseman": {
      "command": "uv",
      "args": ["run", "--directory", "${CLAUDE_PLUGIN_ROOT}/server",
               "wiseman-mcp", "--db", "${CLAUDE_PROJECT_DIR}/.wiseman/wiki.db"]
    }
  }
}
```

서버는 db를 **lazy하게** 열어, 없으면 "아직 위키 없음 → `/summon-wiseman`" 안내. 서버 개선(임베딩·lint·대시보드)은 플러그인 한 곳에서 키우면 모든 프로젝트에 적용.

### 레이어 2 — 프로젝트별 산출물

```
대상 프로젝트/
├── .wiseman/
│   ├── wiki.db        ← LLM 위키 (SQLite, 단일 진실 소스)
│   └── schema.md      ← 위키 구조·워크플로 정의 (지도+규칙)
└── CLAUDE.md          ← `@.wiseman/schema.md` 한 줄 추가됨
```

---

## 5. 데이터 모델 (SQLite, 단일 진실 소스)

```sql
-- 위키 페이지 (정본). content 는 마크다운 텍스트.
CREATE TABLE pages (
  id          INTEGER PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,  -- 예: 'libs/fastapi-auth'
  kind        TEXT NOT NULL,         -- library_doc | project_convention
                                     -- | clean_code | language_pattern | architecture
  library     TEXT,                  -- 예: 'fastapi'
  version     TEXT,                  -- 핀된 설치 버전
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,         -- 마크다운 본문
  source      TEXT,                  -- URL | 코드 경로 | 'derived-principle'
  confidence  TEXT,                  -- high | medium | low
  tags        TEXT,                  -- 쉼표 구분
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- 페이지 간 상호참조 (lint '고아' 판정에 사용)
CREATE TABLE links (
  src_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  dst_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  PRIMARY KEY (src_id, dst_id)
);

-- append-only 연산 기록
CREATE TABLE log (
  id        INTEGER PRIMARY KEY,
  ts        TEXT NOT NULL,
  op        TEXT NOT NULL,           -- ingest | write | lint | summon
  page_slug TEXT,
  note      TEXT
);

-- 메타데이터
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);  -- schema_version, stack, summoned_at ...

-- 전문검색 (BM25)
CREATE VIRTUAL TABLE pages_fts USING fts5(
  title, content, tags, library,
  content='pages', content_rowid='id'
);
-- pages 변경 시 pages_fts 동기화 트리거 포함

-- (향후) 시맨틱 검색: embeddings(page_id, vector BLOB) + sqlite-vec
```

---

## 6. MCP 도구 (질의/복리/점검 인터페이스)

| 도구 | 역할 (카르파시 연산) |
|------|------|
| `ask_wiseman(query, kind?, library?)` | **query** — FTS5 BM25 검색. 관련 페이지 청크 + 출처·버전·confidence 랭킹 반환 |
| `wiki_index()` | 목차/커버리지 개요 (무엇을 아는지) |
| `get_page(slug)` | 페이지 전문 |
| `write_page(slug, kind, ..., content, source)` | **복리** — 페이지 생성/갱신. FTS·links 동기화 + `log` 기록 |
| `lint()` | **lint** — 고아(무링크)·낡음(버전 불일치)·모순 후보 리포트 |

모든 검색 결과는 **출처·버전 동반** — 에이전트가 신뢰도와 "내부 지식 대비 우월성"을 판단하도록. `schema.md`가 "코딩 전 `ask_wiseman`, 새 지식은 `write_page`, 주기적으로 `lint`"를 에이전트 습관으로 안내한다.

---

## 7. 세 가지 연산

### 7-1. `ingest` — `summon-wiseman`이 최초 대량 수행 (§8). 이후 새 라이브러리/문서 증분 흡수.

### 7-2. `query` (검색 + 복리 되먹임)

1. 작업 전 `schema.md` 안내에 따라 `ask_wiseman` 호출
2. 답이 있으면 활용
3. **없거나 부족하면** 즉석 조사 → 답을 내고 → 가치 있으면 `write_page`로 적재(자동, log 기록). 다음엔 위키가 안다 = 복리

### 7-3. `lint` (건강 점검, SQL 기반)

- **고아**: `links`에 인바운드 없는 페이지
- **낡음**: `version`이 현재 설치 버전과 어긋남, 오래된 `updated_at`
- **모순**: 같은 library/topic 페이지 간 상충 후보(에이전트 검토 패스)
- 결과 리포트 + 갱신/병합/삭제 제안

---

## 8. `summon-wiseman` 스킬 (최초 빌드 = 대량 ingest)

### 8-1. 분기 판단
- 의존성 매니페스트 **있으면** → 기존 프로젝트 흐름
- 비어있으면 → 새 프로젝트 흐름

### 8-2. 기존 프로젝트 흐름 (순서 의미 있음)
1. **의존성 식별** — 매니페스트+락파일에서 라이브러리와 **설치된 정확한 버전**
2. **웹 심층 조사** — 핵심 라이브러리별 공식문서+베스트프랙티스, **병렬 서브에이전트** (`deep-research` 활용)
3. **공식문서 부실 시 폴백** — 설치 라이브러리 코드(site-packages/node_modules) 열람
4. **일반 클린코드 원칙**
5. **언어별 안티패턴/베스트프랙티스**
6. **프로젝트 자체** — 아키텍처·관례·CLAUDE.md (참고)
7. **위키 작성** — 정제한 지식을 `write_page`로 적재 + `schema.md` 배치 + CLAUDE.md import 주입 + meta 기록

### 8-3. 새 프로젝트 흐름
1. **브레인스토밍** — 무엇을/어떤 스택을 사용자와 결정
2. 확정 스택에 8-2의 2~7 동일 (6은 계획된 아키텍처 기준)

### 8-4. 병렬화
라이브러리/토픽별 독립 → **병렬 서브에이전트 팬아웃**(`dispatching-parallel-agents`). 각 에이전트가 한 단위를 맡아 구조화된 페이지 초안 반환 → 메인이 `write_page`로 적재.

---

## 9. 품질 게이트 (§1 강제)

위키 확정 **전** 자체 검증:
1. **출처 검사** — `library_doc`은 `source` 필수 (없으면 폐기/`derived-principle`)
2. **버전 핀 검사** — 라이브러리 페이지 `version` 필수
3. **비자명성 스폿체크** — 표본을 "내부 일반 지식보다 나은가" 검토하는 서브에이전트 패스
4. **프로젝트 고유성** — `project_convention`/`architecture` 페이지 ≥1
결과를 summon 종료 시 요약 보고(페이지 수, 커버리지, 폐기 항목).

---

## 10. 배포
- 플러그인 마켓플레이스 (`/plugin install wiseman`) → 스킬 + 서버 + schema 템플릿, MCP 자동 등록
- 서버는 `${CLAUDE_PLUGIN_ROOT}/server`에서 `uv run` (버전이 플러그인과 일치)

---

## 11. 에러 처리

| 상황 | 처리 |
|------|------|
| 웹 검색 불가 | 설치 코드+내부 지식 폴백, `confidence: low` + 경고 |
| 매니페스트 없음 | 새 프로젝트 흐름 |
| db 없음/빈 db | 서버가 "`/summon-wiseman` 실행" 안내 |
| CLAUDE.md 존재 | import 한 줄만 추가(멱등), 기존 보존 |
| `uv` 미설치 | summon 사전점검 후 안내 (향후 npx 폴백) |

---

## 12. 테스트 전략
- **서버 단위** — 시드 db에 `ask_wiseman`/`get_page`/`write_page`/`lint` 기대결과, 빈/없는 db 처리
- **인덱서/트리거** — `write_page` 후 FTS 검색·links·log 동기화
- **품질 게이트** — 출처/버전 없는 페이지 차단
- **스킬 흐름** — 기존/새 프로젝트 분기 (픽스처)
- **CLAUDE.md 주입** — import 멱등성

---

## 13. MVP 범위

**포함:**
- `wiseman` 플러그인 (plugin.json + .mcp.json)
- `summon-wiseman` 스킬 (분기, 병렬 조사, 품질 게이트)
- 범용 Wiseman MCP 서버 (Python+FastMCP, `uv run`)
- SQLite 스키마(pages/links/log/meta + FTS5) + 트리거
- 도구 5종: `ask_wiseman`/`wiki_index`/`get_page`/`write_page`/`lint`
- `schema.md` + CLAUDE.md `@import` 주입
- 복리(query→write_page) & lint 워크플로

**제외 (향후):**
- 벡터 임베딩 / 시맨틱 검색 (`sqlite-vec` + embeddings 테이블)
- Serena식 편집 대시보드
- npx(TypeScript) 서버 런타임
- DB의 git 친화적 export(SQL/JSONL) — §14-4 참조
- 저장소 `teachers-mcp` → `wiseman` 리네임

---

## 14. 결정된 기본값 (제안 → 채택)

1. **재-summon/갱신**: **증분 갱신** 기본 — 매니페스트 버전 vs `pages.version` 비교 → 변경/신규/낡은 라이브러리만 재조사, **`write_page`로 되먹인 페이지는 보존**. `--rebuild`로 전체 재빌드 옵션. *(이유: 복리 누적을 날리지 않음)*
2. **조사 깊이/예산**: **직접 의존성 1개당 병렬 서브에이전트 1개, 동시 8~12개 상한**, 각 제한된 deep-research. 토큰 예산 주어지면 그에 맞춰 스케일. *(폭주 방지)*
3. **라이브러리 선정**: **직접 의존성만.** 조사 전 감지 목록(이름+버전)을 보여주고 사용자가 체크 해제로 선별. 전이 의존성 제외. *(비용·관련성)*
4. **`.wiseman/wiki.db` git**: **기본 커밋**(팀 공유 "공동 두뇌"). 단 SQLite는 바이너리라 **diff/머지가 약함** → 향후 SQL/JSONL export로 git 친화화(향후 범위). `.gitignore` 옵션 제공. 최초 summon 때 한 번 확인. *(공유 가치 우선, 한계 명시)*
5. **복리 자동성**: **자동 `write_page` + log + 공지**("📝 위키에 X 추가"). 매번 확인 안 받음(명백히 가치있고 출처 있는 것만). `lint`가 안전망. *(마찰이 복리를 죽임)*
6. **연산 노출**: **MVP는 `summon-wiseman` 스킬 + MCP 도구 5종.** ingest/query/lint는 schema.md가 도구 호출로 안내(별도 슬래시 커맨드 없음). `/ask-wiseman`·`/wiseman-lint` 편의 커맨드는 패스트팔로우. *(표면 최소화)*

---

## 15. 남은 구현 세부 (계획 단계에서 확정)

- `summon-wiseman`의 대량 적재 경로: 세션 중 MCP `write_page` 다회 호출 vs 번들 인덱서 CLI 일괄 — 쓰기 로직 단일화 전제.
- `schema.md` 주입 방식 세부(멱등 마커 vs `@import` 한 줄) — `@import` 한 줄 권장.
- 도구 설명문(description) 튜닝 — 에이전트가 적시에 `ask_wiseman`/`write_page`를 호출하도록.
