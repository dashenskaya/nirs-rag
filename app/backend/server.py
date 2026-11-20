"""Локальный HTTP API и SQLite. Python 3.10+, внешние пакеты не нужны."""
import base64
import hashlib
import hmac
import json
import mimetypes
import re
import secrets
import sqlite3
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .rag import SearchProvider
from .migrations import apply_migrations

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / 'app' / 'MemeHelper'
MOSCOW = timezone(timedelta(hours=3))
SESSION_AGE = 7 * 24 * 3600


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def text(data, key, minimum=1, maximum=1000):
    value = data.get(key)
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        raise APIError(400, f'Поле {key}: от {minimum} до {maximum} символов')
    return value.strip()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 260000).hex()
    return salt + ':' + digest


def public_user(row):
    return {key: row[key] for key in ('login', 'nickname', 'avatar', 'role')} if row else None


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )
        apply_migrations(self.path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')

        try:
            with db:
                yield db
        finally:
            db.close()

    def create_admin(self, login, password):
        if (
            not re.fullmatch(r'[a-z0-9_.-]{3,20}', login)
            or not 6 <= len(password) <= 128
        ):
            raise ValueError(
                'Логин: 3–20 символов a-z, 0-9, _, ., -; '
                'пароль: 6–128 символов'
            )

        with self.connect() as db:
            db.execute(
                'INSERT INTO users(login,nickname,password_hash,role) '
                'VALUES(?,?,?,?)',
                (
                    login,
                    'Администратор',
                    password_hash(password),
                    'admin'
                )
            )


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, db_path, provider=None):
        self.database = Database(db_path)
        self.provider = provider or SearchProvider()

        with self.database.connect() as db:
            # При подключении RAG каталог должен описывать его базу,
            # не демо-мемы. Старые записи сохраняются.
            for meme in self.provider.catalog:
                db.execute(
                    '''
                    INSERT INTO memes(id, data)
                    VALUES(?, ?)
                    ON CONFLICT(id)
                    DO UPDATE SET data = excluded.data
                    ''',
                    (
                        meme['id'],
                        json.dumps(meme, ensure_ascii=False)
                    )
                )

        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'MemeHelper/1.0'

    def log_message(self, format, *args):
        # Не печатаем содержимое запросов и пароли.
        pass

    def do_GET(self):
        self.handle_request()

    do_POST = do_PATCH = do_PUT = do_DELETE = do_GET

    def handle_request(self):
        self.cookies_out = []
        self.connection.settimeout(130)
        try:
            parsed = urlsplit(self.path)
            self.route = unquote(parsed.path)
            self.params = parse_qs(parsed.query)
            self.cookies = SimpleCookie()
            self.cookies.load(self.headers.get('Cookie', ''))
            host = self.headers.get('Host', '')
            port = self.server.server_port
            if host not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                raise APIError(403, 'Недопустимый адрес сервера')
            if self.command != 'GET':
                if self.headers.get('X-Requested-With') != 'MemeHelper':
                    raise APIError(403, 'Недопустимый источник запроса')
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + host:
                    raise APIError(403, 'Недопустимый источник запроса')
            if not self.route.startswith('/api/'):
                if self.command != 'GET':
                    raise APIError(405, 'Метод не поддерживается')
                return self.static()
            # Выдача изображения по постоянному адресу приложения.
            # image_key и временная ссылка MinIO в JSON чата не сохраняются.

            image_match = re.fullmatch(
                r'/api/memes/([A-Za-z0-9._-]{1,100})/image',
                self.route
            )

            if image_match and self.command == 'GET':

                try:
                    location = self.server.provider.get_image_url(
                        image_match.group(1)
                    )

                except LookupError:
                    raise APIError(
                        404,
                        'Мем или его изображение не найдены'
                    )

                except Exception:
                    traceback.print_exc()

                    raise APIError(
                        502,
                        'Не удалось получить изображение из MinIO'
                    )

                return self.redirect(location)
            data = self.read_json() if self.command in ('POST', 'PATCH', 'PUT') else {}
            with self.server.database.connect() as db:
                self.db = db
                self.user = self.current_user()
                if self.route == '/api/search/stream' and self.command == 'POST':
                    self.handle_stream_search(data)
                    return
                result = self.dispatch(data)
            self.respond(200, result)
        except APIError as error:
            self.respond(error.status, {'error': error.message})
        except Exception:
            traceback.print_exc()
            self.respond(500, {'error': 'Внутренняя ошибка сервера'})

    def read_json(self):
        if self.headers.get_content_type() != 'application/json':
            raise APIError(415, 'Ожидается application/json')
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise APIError(400, 'Неверная длина запроса')
        if size <= 0 or size > 2_000_000:
            raise APIError(413, 'Размер запроса: от 1 байта до 2 МБ')
        try:
            result = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeError):
            raise APIError(400, 'Некорректный JSON')
        if not isinstance(result, dict):
            raise APIError(400, 'Ожидается JSON-объект')
        return result

    def cookie(self, name, value, age=SESSION_AGE):
        self.cookies_out.append(f'{name}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}')

    def token_digest(self):
        token = self.cookies.get('meme_session')
        return hashlib.sha256(token.value.encode()).hexdigest() if token else ''

    def current_user(self):
        return self.db.execute('''SELECT u.* FROM users u JOIN sessions s ON s.login=u.login
                                  WHERE s.token=? AND s.expires>?''', (self.token_digest(), time.time())).fetchone()

    def require(self, role=None):
        if not self.user:
            raise APIError(401, 'UNAUTHORIZED')
        if role and self.user['role'] != role:
            raise APIError(403, 'FORBIDDEN')
        return self.user['login']

    def new_session(self, login):
        token = secrets.token_urlsafe(32)
        self.db.execute('DELETE FROM sessions WHERE expires<? OR token=?', (time.time(), self.token_digest()))
        self.db.execute('INSERT INTO sessions VALUES(?,?,?)',
                        (hashlib.sha256(token.encode()).hexdigest(), login, time.time() + SESSION_AGE))
        self.cookie('meme_session', token)

    def _send_sse_event(self, event, payload):
        """Отправляет одно событие Server-Sent Events клиенту."""
        body = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False
        )
        frame = f'event: {event}\ndata: {body}\n\n'.encode('utf-8')
        self.wfile.write(frame)
        self.wfile.flush()

    def handle_stream_search(self, data):
        """Потоковый HTTP endpoint поиска; история чата не передаётся в RAG."""
        # Проверяем запрос до отправки SSE-заголовков, чтобы ошибки валидации
        # возвращались обычным JSON-ответом с корректным HTTP-статусом.
        query = text(data, 'query', 1, 1000)
        who = (
            'user:' + self.user['login']
            if self.user
            else self.guest()
        )

        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache, no-transform')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Accel-Buffering', 'no')
        for cookie in self.cookies_out:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()

        def emit(event, payload):
            # Клиент использует только эти типы событий. Не принимаем
            # произвольные имена событий от подключённого RAG-провайдера.
            if event not in {'status', 'answer', 'result'}:
                return
            self._send_sse_event(event, payload)

        try:
            emit('status', {'message': 'Ищу подходящие мемы…'})
            response = self.server.provider.stream_search(
                query,
                on_event=emit
            )
            status = 'success' if response['results'] else 'empty'
            ids = list(dict.fromkeys(
                item['meme']['id'] for item in response['results']
            ))

            if response['results']:
                for item in response['results']:
                    self.db.execute(
                        'INSERT OR REPLACE INTO memes VALUES(?,?)',
                        (
                            item['meme']['id'],
                            json.dumps(item['meme'], ensure_ascii=False)
                        )
                    )

            self.db.execute(
                'INSERT INTO events(id,query,status,at,who,meme_ids) VALUES(?,?,?,?,?,?)',
                (
                    secrets.token_hex(16),
                    query,
                    status,
                    int(time.time() * 1000),
                    who,
                    json.dumps(ids)
                )
            )
            self._send_sse_event('done', response)

        except (BrokenPipeError, ConnectionResetError):
            # Клиент закрыл вкладку или отменил запрос. Не пытаемся
            # отправить второй HTTP-ответ в уже закрытое соединение.
            return
        except Exception:
            traceback.print_exc()
            self.db.execute(
                'INSERT INTO events(id,query,status,at,who,meme_ids) VALUES(?,?,?,?,?,?)',
                (
                    secrets.token_hex(16),
                    query,
                    'error',
                    int(time.time() * 1000),
                    who,
                    '[]'
                )
            )
            try:
                self._send_sse_event(
                    'error',
                    {'error': 'Не удалось получить ответ от модуля поиска'}
                )
            except (BrokenPipeError, ConnectionResetError):
                return

    def dispatch(self, data):
        route, method = self.route, self.command
        if route == '/api/health' and method == 'GET':
            return {'status': 'ok', 'searchMode': self.server.provider.mode}
        if route == '/api/me' and method == 'GET':
            return public_user(self.user)
        if route in ('/api/auth/register', '/api/auth/login') and method == 'POST':
            login = text(data, 'login', 3, 20).lower()
            password = data.get('password')
            if not re.fullmatch(r'[a-z0-9_.-]{3,20}', login) or not isinstance(password, str) or not 6 <= len(password) <= 128:
                raise APIError(400, 'Проверьте логин (3–20 символов) и пароль (6–128 символов)')
            if route.endswith('register'):
                nickname = data.get('nickname') or login
                nickname = text({'nickname': nickname}, 'nickname', 1, 30)
                try:
                    self.db.execute('INSERT INTO users(login,nickname,password_hash) VALUES(?,?,?)',
                                    (login, nickname, password_hash(password)))
                except sqlite3.IntegrityError:
                    raise APIError(409, 'Пользователь с таким логином уже есть')
            user = self.db.execute('SELECT * FROM users WHERE login=?', (login,)).fetchone()
            stored = user['password_hash'] if user else password_hash('dummy-password')
            if not hmac.compare_digest(stored, password_hash(password, stored.split(':')[0])) or not user:
                raise APIError(401, 'Неверный логин или пароль')
            self.new_session(login)
            return public_user(user)
        if route == '/api/auth/logout' and method == 'POST':
            self.db.execute('DELETE FROM sessions WHERE token=?', (self.token_digest(),))
            self.cookie('meme_session', '', 0)
            return {'ok': True}
        if route == '/api/me' and method == 'PATCH':
            login = self.require('user')
            nickname = text(data, 'nickname', 1, 30)
            avatar = data.get('avatar')
            if avatar is not None:
                if not isinstance(avatar, str) or len(avatar) > 300_000 or not re.fullmatch(r'data:image/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+', avatar):
                    raise APIError(400, 'Фото: JPEG, PNG или WebP до 300 КБ в формате data URL')
                try:
                    raw = base64.b64decode(avatar.split(',', 1)[1], validate=True)
                    if not (raw.startswith(b'\xff\xd8\xff') or raw.startswith(b'\x89PNG\r\n\x1a\n') or (raw[:4] == b'RIFF' and raw[8:12] == b'WEBP')):
                        raise ValueError()
                except ValueError:
                    raise APIError(400, 'Некорректное изображение')
            self.db.execute('UPDATE users SET nickname=?,avatar=? WHERE login=?', (nickname, avatar, login))
            return public_user(self.db.execute('SELECT * FROM users WHERE login=?', (login,)).fetchone())
        if route == '/api/chats' and method == 'GET':
            login = self.require('user')
            return [dict(row) for row in self.db.execute('SELECT id,title,updated_at AS updatedAt FROM chats WHERE login=? ORDER BY updated_at DESC', (login,))]
        match = re.fullmatch(r'/api/chats/([A-Za-z0-9_-]{1,100})', route)
        if match and method in ('GET', 'PUT', 'DELETE'):
            login = self.require('user')
            chat_id = match[1]
            existing = self.db.execute('SELECT * FROM chats WHERE id=?', (chat_id,)).fetchone()
            if existing and existing['login'] != login:
                raise APIError(404, 'Чат не найден')
            if method == 'GET':
                if not existing:
                    raise APIError(404, 'Чат не найден')
                return {'id': chat_id, 'title': existing['title'], 'updatedAt': existing['updated_at'], 'messages': json.loads(existing['messages'])}
            if method == 'DELETE':
                if not existing:
                    raise APIError(404, 'Чат не найден')
                self.db.execute('DELETE FROM chats WHERE id=? AND login=?', (chat_id, login))
                return {'ok': True}
            if data.get('id') != chat_id:
                raise APIError(400, 'ID чата не совпадает с адресом')
            title = text(data, 'title', 1, 200)
            messages = data.get('messages')
            if not isinstance(messages, list) or len(messages) > 500:
                raise APIError(400, 'В чате допускается до 500 сообщений')
            for message in messages:
                if not isinstance(message, dict) or message.get('role') not in ('user', 'assistant'):
                    raise APIError(400, 'Некорректное сообщение')
                if message['role'] == 'user':
                    text(message, 'text', 1, 1000)
                elif message.get('status') not in ('success', 'empty', 'error'):
                    raise APIError(400, 'Некорректный статус сообщения')
                elif message['status'] == 'success':
                    from .rag import validate_response
                    try:
                        validate_response({'results': message.get('results'), 'answer': message.get('answer', ''), 'sources': message.get('sources', [])})
                    except ValueError:
                        raise APIError(400, 'Некорректный результат поиска в истории')
            now = int(time.time() * 1000)
            self.db.execute('''INSERT INTO chats VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE
                               SET title=excluded.title,updated_at=excluded.updated_at,messages=excluded.messages
                               WHERE chats.login=excluded.login''', (chat_id, login, title, now, json.dumps(messages, ensure_ascii=False)))
            return {'id': chat_id, 'title': title, 'updatedAt': now, 'messages': messages}
        if route == '/api/search' and method == 'POST':
            query = text(data, 'query', 1, 1000)
            try:
                response = self.server.provider.search(query)
                status = 'success' if response['results'] else 'empty'
            except Exception:
                traceback.print_exc()
                response, status = None, 'error'
            who = 'user:' + self.user['login'] if self.user else self.guest()
            ids = list(dict.fromkeys(item['meme']['id'] for item in response['results'])) if response else []
            if response:
                for item in response['results']:
                    self.db.execute('INSERT OR REPLACE INTO memes VALUES(?,?)', (item['meme']['id'], json.dumps(item['meme'], ensure_ascii=False)))
            self.db.execute('INSERT INTO events(id,query,status,at,who,meme_ids) VALUES(?,?,?,?,?,?)',
                            (secrets.token_hex(16), query, status, int(time.time() * 1000), who, json.dumps(ids)))
            # Событие ошибки тоже сохраняется; исключение за пределами транзакции его бы отменило.
            if status == 'error':
                self.db.commit()
                raise APIError(502, 'Не удалось получить ответ от модуля поиска')
            return response
        if route.startswith('/api/admin/'):
            self.require('admin')
            return self.admin(route, method, data)
        raise APIError(404, 'Адрес API не найден или метод не поддерживается')

    def guest(self):
        item = self.cookies.get('meme_guest')
        value = item.value if item and re.fullmatch(r'[a-f0-9]{32}', item.value) else secrets.token_hex(16)
        if not item or value != item.value:
            self.cookie('meme_guest', value, 365 * 86400)
        return 'guest:' + value

    def admin(self, route, method, data=None):
        if route == '/api/admin/memes' and method == 'POST':
            meme_id = text(data, 'id', 1, 100)
            name = text(data, 'name', 1, 200)
            description = text(data, 'description', 1, 8000)
            image_key = text(data, 'image_key', 1, 1024)
            history = data.get('history', '')
            tags = data.get('tags', [])
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise APIError(400, 'Поле tags должно быть списком строк')
            if not isinstance(history, str) or len(history.strip()) > 8000:
                raise APIError(
                    400,
                    'Поле history должно содержать не более 8000 символов'
                )
            try:
                saved = self.server.provider.add_meme(
                    meme_id=meme_id,
                    name=name,
                    description=description,
                    history=history.strip(),
                    image_key=image_key,
                    tags=tags,
                )
            except ValueError as error:
                raise APIError(400, str(error))
            except RuntimeError as error:
                raise APIError(503, str(error))
            # Обновляем служебный каталог для существующей аналитики.
            for item in self.server.provider.catalog:
                self.db.execute(
                    'INSERT OR REPLACE INTO memes VALUES(?,?)',
                    (
                        item['id'],
                        json.dumps(item, ensure_ascii=False)
                    )
                )
            return {
                'ok': True,
                'meme': saved
            }
        if route == '/api/admin/stats' and method == 'GET':
            period = self.params.get('period', ['week'])[0]
            if period not in ('day', 'week'):
                raise APIError(400, 'Период: day или week')
            today = datetime.now(MOSCOW).replace(hour=0, minute=0, second=0, microsecond=0)
            days = [int((today - timedelta(days=6-i)).timestamp() * 1000) for i in range(7)]
            events = self.db.execute('SELECT * FROM events WHERE at>=?', (days[0],)).fetchall()
            selected = [e for e in events if e['at'] >= (days[-1] if period == 'day' else days[0])]
            who = {e['who'] for e in events}
            return {'period': period, 'total': len(selected),
                    'byDay': [{'date': day, 'count': sum(day <= e['at'] < day + 86400000 for e in events)} for day in days],
                    'users': {'guests': sum(w.startswith('guest:') for w in who), 'registered': sum(w.startswith('user:') for w in who)},
                    'empty': sum(e['status'] == 'empty' for e in selected), 'errors': sum(e['status'] == 'error' for e in selected)}
        if route == '/api/admin/memes' and method == 'GET':
            counts = {}
            for row in self.db.execute('SELECT meme_ids FROM events WHERE status="success"'):
                for meme_id in json.loads(row['meme_ids']):
                    counts[meme_id] = counts.get(meme_id, 0) + 1
            memes = [json.loads(r['data']) for r in self.db.execute('SELECT data FROM memes')]
            info = lambda m: {k: m[k] for k in ('id', 'name', 'image')}
            return {'top': sorted([{**info(m), 'shows': counts[m['id']]} for m in memes if counts.get(m['id'])], key=lambda m: (-m['shows'], m['id'])),
                    'dead': [info(m) for m in memes if not counts.get(m['id'])]}
        if route == '/api/admin/empty-queries' and method == 'GET':
            return [dict(r) for r in self.db.execute('SELECT id,query,at FROM events WHERE status="empty" AND hidden=0 ORDER BY at DESC')]
        match = re.fullmatch('/api/admin/empty-queries/([a-f0-9]{32})', route)
        if match and method == 'DELETE':
            result = self.db.execute('UPDATE events SET hidden=1 WHERE id=? AND status="empty" AND hidden=0', (match[1],))
            if not result.rowcount:
                raise APIError(404, 'Запись не найдена')
            return {'ok': True}
        raise APIError(404, 'Адрес API не найден')


    def redirect(self, location):
        self.send_response(302)
        self.send_header(
            'Location',
            location
        )
        self.send_header(
            'Cache-Control',
            'no-store'
        )
        self.send_header(
            'X-Content-Type-Options',
            'nosniff'
        )
        self.send_header(
            'Content-Length',
            '0'
        )
        self.end_headers()

    def respond(self, status, value):
        body = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        for cookie in self.cookies_out:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def static(self):
        route = '/admin.html' if self.route in ('/admin', '/admin/') else self.route
        route = '/index.html' if route == '/' else route
        file = (WEB / route.lstrip('/')).resolve()
        if WEB.resolve() not in file.parents or not file.is_file() or file.suffix.lower() not in ('.html', '.js', '.css', '.jpg', '.png', '.ico'):
            raise APIError(404, 'Файл не найден')
        content = file.read_bytes()
        kind = mimetypes.guess_type(file.name)[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', kind + ('; charset=utf-8' if file.suffix in ('.html', '.js', '.css') else ''))
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(content)
