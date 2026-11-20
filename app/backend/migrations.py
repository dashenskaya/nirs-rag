"""Применение версионированных SQL-миграций SQLite."""

from __future__ import annotations

import argparse
import sqlite3
import time

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

MIGRATIONS_DIR = ROOT / 'migrations'

DEFAULT_DB = ROOT / 'var' / 'memehelper.sqlite3'


def apply_migrations(
    db_path: str | Path = DEFAULT_DB
) -> list[str]:

    """
    Применяет ещё не выполненные миграции.

    Возвращает список применённых файлов.
    """

    path = Path(db_path).resolve()

    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        path,
        timeout=30
    )

    try:

        connection.execute(
            'PRAGMA foreign_keys=ON'
        )

        connection.execute(
            'PRAGMA journal_mode=WAL'
        )

        connection.execute('''
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at INTEGER NOT NULL
            )
        ''')

        connection.commit()

        applied_now = []

        files = sorted(
            MIGRATIONS_DIR.glob('[0-9][0-9][0-9]_*.sql')
        )

        for migration_file in files:

            prefix = migration_file.name.split('_', 1)[0]

            version = int(prefix)

            already_applied = connection.execute(
                '''
                SELECT 1
                FROM schema_migrations
                WHERE version=?
                ''',
                (version,)
            ).fetchone()

            if already_applied:
                continue

            sql = migration_file.read_text(
                encoding='utf-8'
            )

            script = (
                'BEGIN IMMEDIATE;\n'
                + sql
                + '\nINSERT INTO schema_migrations'
                '(version,name,applied_at) VALUES('
                + str(version)
                + ','
                + "'"
                + migration_file.stem.replace("'", "''")
                + "',"
                + str(int(time.time()))
                + ');\nCOMMIT;'
            )

            try:

                connection.executescript(script)

            except Exception:

                if connection.in_transaction:
                    connection.rollback()

                raise

            applied_now.append(
                migration_file.name
            )

        return applied_now

    finally:

        connection.close()


def main():

    parser = argparse.ArgumentParser(
        description='Применение миграций Meme Helper'
    )

    parser.add_argument(
        '--db',
        type=Path,
        default=DEFAULT_DB
    )

    args = parser.parse_args()

    applied = apply_migrations(args.db)

    if applied:

        print(
            'Применены миграции: '
            + ', '.join(applied)
        )

    else:

        print(
            'База данных уже актуальна.'
        )


if __name__ == '__main__':
    main()
