---
name: summon-wiseman
description: Use to build or refresh this project's Wiseman — a codebase-specific LLM wiki of best practices, library docs, and conventions. Run when the user wants the agent to learn the project deeply before coding (e.g. "/summon-wiseman").
---

# Summon Wiseman

현재 프로젝트를 분석·심층 조사하여, 그 코드베이스 전용 LLM 위키(Wiseman)를
`.wiseman/wiki.db`에 구축한다. 핵심 기준: **위키 답은 모델 내부 지식보다
반드시 나아야 한다** — 최신·버전핀·출처보유·프로젝트고유·비자명.

위키 쓰기는 모두 `wiseman` MCP 서버의 `write_page` 도구로 한다(단일 쓰기 경로).
플러그인이 MCP를 자동 등록하므로 도구는 이미 사용 가능하다.

## 0. 분기 판단

- 의존성 매니페스트(`pyproject.toml`/`package.json`/`go.mod` 등)가 있으면 → **기존 프로젝트 흐름(1)**
- 비어 있으면 → **새 프로젝트 흐름**: 먼저 brainstorming으로 무엇을/어떤 스택을
  만들지 사용자와 정한 뒤, 확정 스택에 대해 흐름(1)의 2~7을 수행.

## 1. 기존 프로젝트 흐름 (순서 의미 있음)

1. **의존성 식별**: 매니페스트+락파일에서 라이브러리와 **설치된 정확한 버전**을
   수집한다. **직접 의존성만** 대상으로 한다(전이 의존성 제외).
2. **사용자 선별**: 감지한 라이브러리 목록(이름+버전)을 보여주고, 조사할 것을
   사용자가 체크 해제로 줄이게 한다(비용·관련성).
3. **병렬 심층 조사**: 선별된 라이브러리/토픽마다 **서브에이전트를 병렬로 팬아웃**
   한다(동시 8~12개 상한). 각 에이전트는 한 단위를 맡아: 공식 문서+베스트 프랙티스를
   웹 심층 검색하고(가능하면 `deep-research` 스킬 활용), 공식 문서가 부실하면
   설치된 실제 라이브러리 코드(site-packages/node_modules)를 읽어 근거를 확보하고,
   구조화된 페이지 초안(슬러그/제목/본문/출처/버전/태그/링크)을 반환한다.
4. **일반 원칙 보강**: 클린코드 원칙, 언어별 안티패턴/베스트 프랙티스를 페이지로 추가.
5. **프로젝트 반영**: 기존 아키텍처·코드 관례·CLAUDE.md를 참고해
   `project_convention`/`architecture` 페이지를 작성(이 프로젝트만의 것).
6. **품질 게이트** (적재 전 검증):
   - `library_doc`은 `source` 필수(없으면 폐기 또는 `derived-principle`).
   - 라이브러리 페이지는 `version` 필수(설치 버전 일치).
   - 표본 페이지가 "모델 내부 일반 지식보다 나은가" 자가 점검(일반론뿐이면 재조사).
   - `project_convention`/`architecture` 최소 1개.
7. **적재 & 배선**:
   - 검증 통과한 페이지를 `write_page(...)`로 적재(관련 페이지는 `links`로 연결).
   - 플러그인 템플릿의 `schema.md`를 `.wiseman/schema.md`로 복사한다.
   - 프로젝트 `CLAUDE.md`에 `@.wiseman/schema.md` import 한 줄을 **멱등하게** 추가한다
     (이미 있으면 두 번 넣지 않는다; CLAUDE.md가 없으면 생성). 기존 내용은 보존.

## 2. 재실행(증분 갱신)

위키가 이미 있으면 **증분 갱신**이 기본이다: 매니페스트 버전과 각 라이브러리 페이지의
`version`을 비교해 변경/신규/낡은 라이브러리만 다시 조사하고, `write_page`로
되먹인(복리) 페이지는 보존한다. 사용자가 `--rebuild`(전체 재빌드)를 요청하면
처음부터 다시 만든다.

## 3. 마무리 보고

적재된 페이지 수, 라이브러리별 커버리지, 폐기 항목, `lint()` 결과를 사용자에게
요약 보고한다. 이후 코딩 시 `schema.md` 지침에 따라 `ask_wiseman`을 먼저 쓰라고 안내.

## git

`.wiseman/`는 기본적으로 커밋을 권장한다(팀 공유 "공동 두뇌"). 단 `wiki.db`는
바이너리라 diff/머지가 약하다는 점을 사용자에게 알리고, 원치 않으면 `.gitignore`에
추가하도록 안내한다.
