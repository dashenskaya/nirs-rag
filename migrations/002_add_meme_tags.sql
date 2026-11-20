-- Добавляем ручные теги в ту же таблицу, где хранятся остальные поля мема.
-- Теги хранятся JSON-массивом русскоязычных строк.
ALTER TABLE meme_catalog
ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';

-- Пересоздаём поисковую таблицу, чтобы поле tags участвовало в BM25.
CREATE TABLE meme_terms_new (
    meme_id TEXT NOT NULL REFERENCES meme_catalog(id) ON DELETE CASCADE,
    field TEXT NOT NULL CHECK(field IN ('name','description','history','tags')),
    token TEXT NOT NULL,
    tf INTEGER NOT NULL CHECK(tf > 0),
    PRIMARY KEY(meme_id, field, token)
);

INSERT INTO meme_terms_new(meme_id, field, token, tf)
SELECT meme_id, field, token, tf FROM meme_terms;

DROP TABLE meme_terms;
ALTER TABLE meme_terms_new RENAME TO meme_terms;

CREATE INDEX IF NOT EXISTS meme_terms_token_idx ON meme_terms(token,field);
CREATE INDEX IF NOT EXISTS meme_terms_meme_idx ON meme_terms(meme_id);
