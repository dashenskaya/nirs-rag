"""Запуск Meme Helper."""

import argparse
import getpass
import os

from pathlib import Path

from app.backend.config import load_env_file
from app.backend.migrations import apply_migrations
from app.backend.rag import SearchProvider
from app.backend.server import Database, Server


def main():

    load_env_file()

    parser = argparse.ArgumentParser(
        description='Локальный сервер Meme Helper'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8000
    )

    parser.add_argument(
        '--db',
        type=Path,
        default=Path(__file__).resolve().parent
        / 'var'
        / 'memehelper.sqlite3'
    )

    parser.add_argument(
        '--create-admin',
        metavar='LOGIN'
    )

    args = parser.parse_args()

    os.environ['MEME_DB_PATH'] = str(
        args.db.resolve()
    )

    # Применяем миграции перед использованием базы.
    apply_migrations(args.db)

    # Создание администратора.
    if args.create_admin:

        password = getpass.getpass(
            'Пароль администратора: '
        )

        if password != getpass.getpass(
            'Повторите пароль: '
        ):

            parser.error(
                'Пароли не совпадают'
            )

        try:

            Database(args.db).create_admin(
                args.create_admin,
                password
            )

        except Exception as error:

            parser.error(str(error))

        print(
            'Администратор создан. Теперь запустите сервер.'
        )

        return

    try:

        # Используем новую RAG-систему.
        provider_target = (
            os.environ.get('RAG_PROVIDER')
            or 'app.backend.meme_rag:search'
        )

        provider = SearchProvider(
            provider_target
        )

        server = Server(
            ('127.0.0.1', args.port),
            args.db,
            provider
        )

    except Exception as error:

        parser.error(str(error))

    print(
        f'Meme Helper: http://127.0.0.1:{server.server_port}',
        flush=True
    )

    print(
        f'Поиск: {provider.mode}. Остановка: Ctrl+C.',
        flush=True
    )

    if provider.mode == 'rag':

        print(
            'Поиск: pymorphy3 + BM25 + LLM; '
            'изображения: серверные ссылки MinIO.',
            flush=True
        )

    try:

        server.serve_forever()

    except KeyboardInterrupt:

        print('\nСервер остановлен.')

    finally:

        server.server_close()


if __name__ == '__main__':
    main()
