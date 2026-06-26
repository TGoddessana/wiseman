EMPTY_MSG = (
    "이 프로젝트에는 아직 Wiseman 위키가 없습니다. "
    "`/summon-wiseman`을 실행해 위키를 구축하세요. "
    "(No wiki yet for this project — run /summon-wiseman.)"
)


def ask_wiseman(repo, query, kind=None, library=None, limit=10):
    if repo.is_empty():
        return {"status": "empty", "message": EMPTY_MSG}
    return {"status": "ok",
            "results": repo.search(query, kind=kind, library=library, limit=limit)}


def wiki_index(repo):
    if repo.is_empty():
        return {"status": "empty", "message": EMPTY_MSG}
    return {"status": "ok", "index": repo.index()}


def get_page(repo, slug):
    page = repo.get_page(slug)
    if page is None:
        return {"status": "not_found", "slug": slug}
    return {"status": "ok", "page": page}


def write_page(repo, **kwargs):
    return {"status": "ok", "page": repo.write_page(**kwargs)}


def lint(repo):
    if repo.is_empty():
        return {"status": "empty", "message": EMPTY_MSG}
    return {"status": "ok", "report": repo.lint()}
