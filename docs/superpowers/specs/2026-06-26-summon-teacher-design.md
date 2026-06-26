# `/summon-teacher` 설계 문서

- 작성일: 2026-06-26
- 상태: 설계 확정 대기 (사용자 리뷰)
- 한 줄 요약: 현재 프로젝트를 분석·심층 조사하여, **그 프로젝트에 딱 맞는 "선생님(Teacher)"** — 즉 프로젝트 전용 지식이 담긴 MCP 서버 — 를 만들어주는 Claude Code 플러그인 + 스킬.

---

## 1. 목적과 핵심 가치 기준

`teachers-mcp`는 **"우리 프로젝트에 딱 맞는 LLM 위키"** 를 만든다. 코딩 중 Claude가 "선생님에게 물어보면", 그 프로젝트의 실제 스택·버전·관례·함정에 맞는 답을 받는다.

### 절대적 성공 기준 (Non-negotiable)

> **티처에게 물어서 얻은 답은, 모델이 자기 내부 지식만으로 짜는 것보다 반드시 더 나아야 한다.**

둘이 다를 게 없으면 티처를 만들 이유가 없다. 따라서 저장되는 모든 지식은 다음을 만족해야 한다:

1. **최신성** — 웹 심층 조사로 현재 버전 기준 정보를 수집
2. **버전 핀(pin)** — 프로젝트에 실제로 설치된 버전에 고정
3. **출처(source) 보유** — 공식 문서 URL, 또는 설치 코드 경로, 또는 "유도된 원칙" 명시
4. **프로젝트 고유성** — 일반론이 아니라 이 프로젝트의 스택/아키텍처/CLAUDE.md 관례 반영
5. **비자명성** — 뻔한 내용이 아니라 함정·안티패턴·관례 중심

이 기준은 단순한 목표가 아니라 빌드 파이프라인의 **검증 게이트**로 강제한다(§7).

---

## 2. 전체 아키텍처

두 개의 레이어로 명확히 분리된다.

### 레이어 1 — 플러그인 (배포물, 한 곳에서 관리)

`teachers-mcp` 플러그인은 다음을 번들한다:

- `summon-teacher` **스킬** — 분석·조사·DB 생성 지시문 (빌드 시점)
- **범용 Teacher MCP 서버** — DB를 읽어 검색해주는 빈 껍데기 (질의 시점)
- (향후) 편집 대시보드, 임베딩 인덱서

플러그인 설치 시 MCP 서버가 **자동 등록**된다. 서버 코드는 `${CLAUDE_PLUGIN_ROOT}`에 한 벌만 존재하고, db 경로는 `${CLAUDE_PROJECT_DIR}`로 현재 프로젝트를 자동으로 가리킨다.

```jsonc
// 플러그인의 .mcp.json (또는 plugin.json 의 mcpServers 필드)
{
  "mcpServers": {
    "teacher": {
      "command": "uv",
      "args": [
        "run", "--directory", "${CLAUDE_PLUGIN_ROOT}/server",
        "teacher-mcp",
        "--db", "${CLAUDE_PROJECT_DIR}/.teacher/teacher.db"
      ]
    }
  }
}
```

### 레이어 2 — 프로젝트별 산출물 (가벼움)

`/summon-teacher` 실행 시 **프로젝트에 생기는 산출물은 `.teacher/teacher.db` 단 하나**다(+ 선택적으로 `.teacher/meta.json`). 서버 코드는 프로젝트에 복제되지 않는다.

```
대상 프로젝트/
└── .teacher/
    ├── teacher.db      ← 이 프로젝트의 지식 (SQLite, 단일 진실 소스)
    └── meta.json       ← summon 메타데이터 (선택: 스택, 일시, 스키마 버전)
```

### 왜 이 구조인가

- 서버 버그 수정·임베딩·대시보드를 플러그인 한 곳에서 키우면 **모든 프로젝트에 즉시 적용**
- 프로젝트는 db 하나만 가지므로 가볍고, git 공유도 선택 가능
- "선생님은 계속 똑똑해지는 존재"라는 컨셉과 일치

---

## 3. 사용자 흐름

### 3-1. 최초 1회

```
/plugin install teachers
→ summon-teacher 스킬 + 범용 Teacher 서버가 자동 설치/등록됨
→ 아직 어떤 프로젝트에도 db가 없으므로, 서버는 "선생님이 아직 없습니다" 상태
```

### 3-2. 프로젝트마다

```
/summon-teacher
→ (분기) 진행 중 프로젝트인가, 새 프로젝트인가 판단
→ 분석 + 웹 심층 조사 (병렬 서브에이전트)
→ 지식을 .teacher/teacher.db 로 빌드
→ 사용자에게 요약 보고 + 활성화 확인
→ 이후 코딩/다른 스킬에서 teacher MCP 도구로 질의
```

서버는 매 질의마다 db를 **lazy하게 읽으므로**, db가 생기는 즉시 답하기 시작한다(서버 재시작 불필요). db가 없으면 "선생님이 아직 없습니다. `/summon-teacher` 실행하세요"를 반환한다.

---

## 4. `summon-teacher` 스킬 (빌드 시점)

### 4-1. 분기 판단

스킬은 먼저 프로젝트 상태를 확인한다:

- 소스 코드/의존성 매니페스트(`pyproject.toml`, `package.json` 등)가 **있으면** → **기존 프로젝트 흐름**
- 비어있거나 초기 상태면 → **새 프로젝트 흐름**

### 4-2. 기존 프로젝트 흐름

사용자가 제시한 추출 파이프라인을 따른다(순서 의미 있음):

1. **의존성 식별** — 매니페스트 + 락파일에서 라이브러리와 **설치된 정확한 버전** 수집
2. **웹 심층 조사** — 각 핵심 라이브러리의 공식 문서 + 베스트 프랙티스를 (병렬 서브에이전트로) 심층 검색. *환경에 `deep-research` 스킬이 있으면 활용.*
3. **공식 문서 부실 시 폴백** — 문서가 없거나 빈약하면 설치된 실제 라이브러리 코드(site-packages / node_modules)를 읽어 근거 확보
4. **일반 클린코드 원칙** 고려
5. **언어별 안티패턴 / 베스트 프랙티스** 고려
6. **프로젝트 자체** — 기존 아키텍처, 코드 관례, `CLAUDE.md` 등을 참고 수준으로 반영
7. **DB 빌드** — 위 지식을 정제하여 `teacher.db`에 기록

### 4-3. 새 프로젝트 흐름

1. **브레인스토밍** — 무엇을 만들지, 어떤 스택/라이브러리를 쓸지 사용자와 함께 결정
2. 확정된 스택에 대해 **4-2의 2~7 단계를 동일하게** 수행 (분석할 기존 코드가 없으므로 6단계는 계획된 아키텍처 기준)

### 4-4. 병렬화

라이브러리/토픽별로 독립적이므로, 조사 단계는 **병렬 서브에이전트로 팬아웃**한다(`dispatching-parallel-agents` 패턴). 각 에이전트는 한 라이브러리(또는 한 토픽)를 맡아 구조화된 지식 엔트리 목록을 반환한다.

---

## 5. 지식 데이터 모델 (SQLite, 단일 진실 소스)

마크다운 소스 파일은 두지 않는다(파일↔인덱스 정합성 문제 회피). SQLite가 **유일한 저장소**이며, 향후 편집은 Serena식 대시보드로 한다.

### 5-1. 스키마 (MVP)

```sql
-- 지식 엔트리 (정본)
CREATE TABLE entries (
  id          INTEGER PRIMARY KEY,
  kind        TEXT NOT NULL,   -- 'library_doc' | 'project_convention'
                               -- | 'clean_code' | 'language_pattern' | 'architecture'
  library     TEXT,            -- 예: 'fastapi' (해당 없으면 NULL)
  version     TEXT,            -- 예: '0.115.2' (핀된 버전)
  topic       TEXT,            -- 예: 'authentication', 'dependency-injection'
  title       TEXT NOT NULL,   -- 한 줄 제목
  content     TEXT NOT NULL,   -- 본문 (마크다운)
  source      TEXT,            -- URL | 파일 경로 | 'derived-principle'
  confidence  TEXT,            -- 'high' | 'medium' | 'low'
  tags        TEXT,            -- 쉼표 구분 키워드
  created_at  TEXT NOT NULL
);

-- 전문검색 인덱스 (BM25 랭킹)
CREATE VIRTUAL TABLE entries_fts USING fts5(
  title, topic, content, tags,
  content='entries', content_rowid='id'
);
-- entries INSERT/UPDATE/DELETE 시 entries_fts 동기화하는 트리거 포함

-- summon 메타데이터
CREATE TABLE meta (
  key   TEXT PRIMARY KEY,      -- 'project_name', 'summoned_at',
                               -- 'stack', 'schema_version'
  value TEXT
);
```

### 5-2. 향후 확장 (MVP 범위 밖, 스키마는 미리 대비)

- `embeddings(entry_id, vector BLOB)` 테이블 추가 → `sqlite-vec` 로 의미 검색
- FTS5(키워드) + 벡터(의미) **하이브리드 검색**으로 자연스럽게 진화
- 저장 계층(entries)은 그대로이므로 변경 없음

---

## 6. Teacher MCP 서버 (질의 시점)

범용 서버. `--db` 인자로 받은 SQLite를 lazy하게 읽는다. Context7의 `resolve-library-id` + `get-library-docs` 패턴을 로컬·구조화 버전으로 미러링한다.

### 6-1. 도구 (MVP)

| 도구 | 역할 |
|------|------|
| `list_topics()` | 이 프로젝트 선생님이 아는 라이브러리/토픽 목록 반환 (에이전트가 "무엇을 물을 수 있는지" 파악). Context7의 `resolve-library-id` 대응 |
| `ask_teacher(query, topic?, library?)` | FTS5 BM25 검색. 관련 엔트리(제목·본문·**출처**·버전·confidence) 랭킹 반환. Context7의 `get-library-docs` 대응 |
| `get_entry(id)` | 특정 엔트리 전문 반환 |

도구는 항상 **출처와 버전을 함께 반환**한다 — 에이전트가 신뢰도를 판단하고, 일반 지식 대비 우월성을 확인할 수 있도록.

### 6-2. 빈/없는 DB 처리

- db 파일 없음 → 모든 도구가 "선생님이 아직 없습니다. `/summon-teacher`를 실행하세요" 안내
- db는 있으나 엔트리 0개 → "선생님이 비어있습니다" 안내

---

## 7. 품질 게이트 (§1 기준 강제)

빌드 파이프라인은 db 확정 **전에** 자체 검증한다:

1. **출처 검사** — 모든 `library_doc` 엔트리는 `source`(URL 또는 코드 경로)를 가져야 한다. 없으면 폐기하거나 `derived-principle`로 명시.
2. **버전 핀 검사** — 라이브러리 엔트리는 `version`이 비어선 안 된다(설치 버전과 일치).
3. **비자명성 스폿체크** — 표본 엔트리 몇 개를 골라 "이게 모델 내부 일반 지식과 다른가? 더 나은가?"를 검토하는 서브에이전트 패스. 일반론뿐이면 재조사.
4. **프로젝트 고유성** — `project_convention` / `architecture` 엔트리가 최소 N개 이상 존재(이 프로젝트만의 무언가가 담겼는지).

검증 결과는 summon 종료 시 사용자에게 **요약 보고**된다(엔트리 수, 라이브러리별 커버리지, 폐기된 항목).

---

## 8. 데이터 흐름 요약

```
[빌드: /summon-teacher]
프로젝트 분석 → 병렬 조사(웹/코드) → 정제 → 품질 게이트 → teacher.db 기록 → 사용자 보고

[질의: 코딩 중]
Claude → teacher MCP (list_topics / ask_teacher) → teacher.db FTS5 검색 → 엔트리+출처 반환 → Claude가 활용
```

---

## 9. 배포

- Claude Code **플러그인 마켓플레이스**로 배포 (`/plugin install teachers`)
- 플러그인이 스킬 + 범용 서버를 번들, MCP 자동 등록
- 서버는 `${CLAUDE_PLUGIN_ROOT}/server`에서 `uv run`으로 실행 (네트워크 불필요, 버전이 플러그인과 일치)

---

## 10. 에러 처리

| 상황 | 처리 |
|------|------|
| 웹 검색 불가(오프라인) | 설치 코드 + 내부 지식으로 폴백, 엔트리 `confidence='low'` + 사용자 경고 |
| 의존성 매니페스트 없음 | 새 프로젝트 흐름(브레인스토밍)으로 전환 |
| db 없음/빈 db | 서버가 안내 메시지 반환 (§6-2) |
| `uv` 미설치 | summon 시 사전 점검 후 설치 안내 (향후 npx 폴백 여지) |
| 재-summon | 기존 db 갱신 정책 필요 (전체 재빌드 vs 증분) — §13 참조 |

---

## 11. 테스트 전략

- **서버 단위 테스트** — 알려진 시드 db에 대해 `list_topics`/`ask_teacher`/`get_entry`가 기대 결과 반환, 빈/없는 db 처리
- **인덱서 단위 테스트** — 엔트리 입력 → FTS5 검색 가능, 트리거 동기화 검증
- **품질 게이트 테스트** — 출처 없는/버전 없는 엔트리가 게이트에 걸리는지
- **스킬 흐름** — 기존/새 프로젝트 분기 판단 (수동 또는 픽스처 기반)

---

## 12. MVP 범위

**포함:**
- `teachers-mcp` 플러그인 구조 (plugin.json + .mcp.json)
- `summon-teacher` 스킬 (기존/새 프로젝트 분기, 병렬 조사, 품질 게이트)
- 범용 Teacher 서버 (Python + FastMCP, `uv run`)
- SQLite 스키마 + FTS5 인덱서
- 3개 도구: `list_topics`, `ask_teacher`, `get_entry`

**제외 (향후):**
- 벡터 임베딩 / 의미 검색 (`sqlite-vec`)
- Serena식 편집 대시보드
- npx(TypeScript) 서버 런타임
- 증분 재-summon

---

## 13. 열린 질문 (구현 계획 전 확정 필요)

1. **재-summon 정책** — 두 번째 `/summon-teacher` 실행 시: 전체 재빌드 vs 증분 갱신 vs 사용자 선택?
2. **조사 깊이/비용** — 라이브러리당 서브에이전트 몇 개까지? 토큰 예산 상한?
3. **핵심 라이브러리 선정** — 모든 의존성을 다 조사하면 비쌈. 직접 의존성만? 사용자 확인 후 선별?
4. **`.teacher/` git 커밋 여부** — db를 팀과 공유(커밋) vs 개인별(gitignore)? 기본값 권장 필요.
5. **도구 이름** — `ask_teacher` 등 네이밍이 에이전트의 호출 유도에 적합한지 (MCP 도구 설명문 튜닝).
