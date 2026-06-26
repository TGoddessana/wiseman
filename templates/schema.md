# Wiseman — 위키 사용 매뉴얼 (this project's "wise man")

이 프로젝트에는 코드베이스 전용 LLM 위키(Wiseman)가 있다. 위키는
`.wiseman/wiki.db`(SQLite, 단일 진실 소스)에 있고, `wiseman` MCP 서버의
도구로 접근한다. **위키 전체를 컨텍스트에 넣지 말 것** — 이 매뉴얼만 상주하고,
내용은 도구로 필요한 만큼만 끌어온다.

## 언제 무엇을 하나 (3연산)

- **query (코딩/설계 전에 항상)**: 라이브러리 사용법·관례·함정이 걸리는 작업을
  시작하기 전에 `ask_wiseman(query, kind?, library?)`로 먼저 위키에 묻는다.
  무엇을 아는지 모르면 `wiki_index()`로 목차를 본다. 특정 페이지 전문은
  `get_page(slug)`.
- **ingest / 복리 (새로 배웠을 때)**: 조사·종합으로 이 프로젝트에 유용하고
  출처가 분명한 새 지식을 얻으면 `write_page(...)`로 위키에 적재한다(복리 루프:
  다음엔 위키가 안다). 라이브러리 지식은 `source`와 `version`을 반드시 채운다.
- **lint (가끔)**: `lint()`로 고아 페이지·출처/버전 누락·낡은 페이지를 점검하고
  갱신한다.

## 품질 기준 (반드시)

위키 답은 **모델 내부 지식보다 나아야** 한다. `write_page` 시:
- `source`: 공식 문서 URL / 설치 코드 경로 / `derived-principle`
- `version`: 설치된 정확한 버전 (라이브러리 지식)
- 일반론이 아니라 **이 프로젝트의 함정·관례·안티패턴** 중심으로.

## 페이지 종류(kind)

`library_doc` · `project_convention` · `clean_code` · `language_pattern` · `architecture`

## slug 규칙

`libs/<library>-<topic>`, `conventions/<topic>`, `patterns/<topic>`,
`architecture/<topic>` 처럼 분류 접두사를 쓴다. 관련 페이지는 `write_page`의
`links`로 연결한다(고아 방지).
