"""Запуск: python run.py. Создание админа: python run.py --create-admin admin."""
import argparse
import getpass
import os
from pathlib import Path

from app.backend.rag import SearchProvider
from app.backend.server import Database, Server


def main():
    parser = argparse.ArgumentParser(description='Локальный сервер Meme Helper')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--db', type=Path, default=Path(__file__).resolve().parent / 'var' / 'memehelper.sqlite3')
    parser.add_argument('--create-admin', metavar='LOGIN')
    args = parser.parse_args()
    if args.create_admin:
        password = getpass.getpass('Пароль администратора: ')
        if password != getpass.getpass('Повторите пароль: '):
            parser.error('Пароли не совпадают')
        try:
            Database(args.db).create_admin(args.create_admin, password)
        except Exception as error:
            parser.error(str(error))
        print('Администратор создан. Теперь запустите сервер.')
        return
    try:
        provider = SearchProvider(os.environ.get('RAG_PROVIDER') or None)
        server = Server(('127.0.0.1', args.port), args.db, provider)
    except Exception as error:
        parser.error(str(error))
    print(f'Meme Helper: http://127.0.0.1:{server.server_port}', flush=True)
    print(f'Поиск: {provider.mode}. Остановка: Ctrl+C.', flush=True)
    if provider.mode == 'demo':
        print('Демонстрационный поиск по двум мемам. BM25 и LLM ещё не подключены.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nСервер остановлен.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
