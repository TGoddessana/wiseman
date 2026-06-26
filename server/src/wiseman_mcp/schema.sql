CREATE TABLE IF NOT EXISTS pages (
  id          INTEGER PRIMARY KEY,
  slug        TEXT UNIQUE NOT NULL,
  kind        TEXT NOT NULL,
  library     TEXT,
  version     TEXT,
  title       TEXT NOT NULL,
  content     TEXT NOT NULL,
  source      TEXT,
  confidence  TEXT NOT NULL DEFAULT 'medium',
  tags        TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
  src_slug TEXT NOT NULL,
  dst_slug TEXT NOT NULL,
  PRIMARY KEY (src_slug, dst_slug)
);

CREATE TABLE IF NOT EXISTS log (
  id        INTEGER PRIMARY KEY,
  ts        TEXT NOT NULL,
  op        TEXT NOT NULL,
  page_slug TEXT,
  note      TEXT
);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS pages_fts USING fts5(
  title, content, tags, library,
  content='pages', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS pages_ai AFTER INSERT ON pages BEGIN
  INSERT INTO pages_fts(rowid, title, content, tags, library)
  VALUES (new.id, new.title, new.content, new.tags, new.library);
END;

CREATE TRIGGER IF NOT EXISTS pages_ad AFTER DELETE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, title, content, tags, library)
  VALUES ('delete', old.id, old.title, old.content, old.tags, old.library);
END;

CREATE TRIGGER IF NOT EXISTS pages_au AFTER UPDATE ON pages BEGIN
  INSERT INTO pages_fts(pages_fts, rowid, title, content, tags, library)
  VALUES ('delete', old.id, old.title, old.content, old.tags, old.library);
  INSERT INTO pages_fts(rowid, title, content, tags, library)
  VALUES (new.id, new.title, new.content, new.tags, new.library);
END;
