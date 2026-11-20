-- Основные таблицы приложения.
-- IF NOT EXISTS сохраняет существующие данные.

CREATE TABLE IF NOT EXISTS users (
    login TEXT PRIMARY KEY,
    nickname TEXT NOT NULL,
    avatar TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    login TEXT NOT NULL REFERENCES users(login),
    expires REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    login TEXT NOT NULL REFERENCES users(login),
    title TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    messages TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memes (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    status TEXT NOT NULL,
    at INTEGER NOT NULL,
    who TEXT NOT NULL,
    meme_ids TEXT NOT NULL,
    hidden INTEGER NOT NULL DEFAULT 0
);


-- Основная таблица мемов.

CREATE TABLE IF NOT EXISTS meme_catalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    history TEXT NOT NULL DEFAULT '',
    image_key TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);


-- Таблица нормализованных поисковых терминов.

CREATE TABLE IF NOT EXISTS meme_terms (
    meme_id TEXT NOT NULL
        REFERENCES meme_catalog(id)
        ON DELETE CASCADE,

    field TEXT NOT NULL
        CHECK(field IN ('name','description','history')),

    token TEXT NOT NULL,

    tf INTEGER NOT NULL
        CHECK(tf > 0),

    PRIMARY KEY(meme_id, field, token)
);


-- Версия поискового индекса.

CREATE TABLE IF NOT EXISTS meme_index_meta (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL
);

INSERT OR IGNORE INTO meme_index_meta(id,version)
VALUES(1,0);


-- Индексы для ускорения запросов.

CREATE INDEX IF NOT EXISTS events_at
ON events(at);

CREATE INDEX IF NOT EXISTS chats_owner
ON chats(login);

CREATE INDEX IF NOT EXISTS meme_terms_token_idx
ON meme_terms(token,field);

CREATE INDEX IF NOT EXISTS meme_terms_meme_idx
ON meme_terms(meme_id);
