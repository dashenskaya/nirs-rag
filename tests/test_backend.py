"""HTTP-интеграция с отдельной временной SQLite; рабочие данные не затрагиваются."""
import http.cookiejar
import json
import contextlib
import io
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from app.backend.server import Server
from app.backend.rag import SearchProvider


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def call(self, path, method='GET', data=None, headers=None):
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(self.base + path, data=body, method=method,
            headers=headers if headers is not None else {'Content-Type': 'application/json', 'X-Requested-With': 'MemeHelper'})
        try:
            response = self.opener.open(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            kind = response.headers.get('Content-Type', '')
            return response.status, json.loads(raw) if 'application/json' in kind else raw

    def register(self, login='dasha'):
        return self.call('/api/auth/register', 'POST', {'login': login, 'nickname': login, 'password': 'secret123'})


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.server = Server(('127.0.0.1', 0), self.path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.client = Client(self.base)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_registration_login_session_and_password_hash(self):
        self.assertEqual(self.client.call('/api/me'), (200, None))
        status, user = self.client.register()
        self.assertEqual(status, 200)
        self.assertNotIn('password', user)
        self.assertEqual(self.client.register()[0], 409)
        cookie = next(c for c in self.client.jar if c.name == 'meme_session')
        self.assertIn('HttpOnly', cookie._rest)
        with self.server.database.connect() as db:
            stored = db.execute('SELECT password_hash FROM users').fetchone()[0]
            self.assertNotIn('secret123', stored)
        self.assertEqual(self.client.call('/api/me')[1]['login'], 'dasha')
        self.assertEqual(self.client.call('/api/auth/logout', 'POST', {})[0], 200)
        self.assertEqual(self.client.call('/api/chats')[0], 401)
        self.assertEqual(self.client.call('/api/auth/login', 'POST', {'login': 'dasha', 'password': 'wrong123'})[0], 401)
        self.assertEqual(self.client.call('/api/auth/login', 'POST', {'login': 'DASHA', 'password': 'secret123'})[0], 200)

    def test_chats_are_private_and_persistent(self):
        self.client.register()
        answer = self.client.call('/api/search', 'POST', {'query': 'спокойной ночи'})[1]
        chat = {'id': 'chat_test', 'title': 'Сон', 'messages': [
            {'role': 'user', 'text': 'спокойной ночи'}, {'role': 'assistant', 'status': 'success', **answer}]}
        self.assertEqual(self.client.call('/api/chats/chat_test', 'PUT', chat)[0], 200)
        other = Client(self.base)
        other.register('nikita')
        self.assertEqual(other.call('/api/chats')[1], [])
        for method, data in [('GET', None), ('DELETE', None), ('PUT', chat)]:
            self.assertEqual(other.call('/api/chats/chat_test', method, data)[0], 404)
        with self.server.database.connect() as db:
            self.assertEqual(json.loads(db.execute('SELECT messages FROM chats').fetchone()[0]), chat['messages'])
        # Новый объект базы и сервера читает тот же файл после перезапуска.
        from app.backend.server import Database
        with Database(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM chats').fetchone()[0], 1)
        self.assertEqual(self.client.call('/api/chats/chat_test')[1]['title'], 'Сон')
        self.assertEqual(self.client.call('/api/chats/chat_test', 'DELETE')[0], 200)
        self.assertEqual(self.client.call('/api/chats')[1], [])

    def test_profile_validation_and_roles(self):
        self.client.register()
        self.assertEqual(self.client.call('/api/me', 'PATCH', {'nickname': 'Дарья', 'avatar': None})[1]['nickname'], 'Дарья')
        self.assertEqual(self.client.call('/api/me', 'PATCH', {'nickname': 'X', 'avatar': 'javascript:alert(1)'})[0], 400)
        self.assertEqual(self.client.call('/api/admin/stats')[0], 403)
        self.assertEqual(Client(self.base).call('/api/admin/stats')[0], 401)
        self.server.database.create_admin('admin', 'admin-secret')
        admin = Client(self.base)
        admin.call('/api/auth/login', 'POST', {'login': 'admin', 'password': 'admin-secret'})
        self.assertEqual(admin.call('/api/chats')[0], 403)
        self.assertEqual(admin.call('/api/me', 'PATCH', {'nickname': 'X', 'avatar': None})[0], 403)

    def test_stream_search_endpoint_emits_sse_and_logs_event(self):
        status, raw = self.client.call(
            '/api/search/stream',
            'POST',
            {'query': 'смешная шутка'}
        )

        self.assertEqual(status, 200)
        stream = raw.decode('utf-8')
        self.assertIn('event: status', stream)
        self.assertIn('event: answer', stream)
        self.assertIn('event: result', stream)
        self.assertIn('event: done', stream)

        done_frame = next(
            frame for frame in stream.split('\n\n')
            if frame.startswith('event: done\n')
        )
        payload = json.loads(
            next(line[5:] for line in done_frame.splitlines() if line.startswith('data:'))
        )
        self.assertEqual(payload['mode'], 'demo')
        self.assertTrue(payload['results'])

        with self.server.database.connect() as db:
            event = db.execute(
                'SELECT query,status,meme_ids FROM events ORDER BY at DESC LIMIT 1'
            ).fetchone()
        self.assertEqual(event['query'], 'смешная шутка')
        self.assertEqual(event['status'], 'success')
        self.assertTrue(json.loads(event['meme_ids']))

    def test_stream_search_endpoint_validates_query_before_starting_stream(self):
        status, value = self.client.call(
            '/api/search/stream',
            'POST',
            {'query': ' '}
        )
        self.assertEqual(status, 400)
        self.assertIn('error', value)

    def test_search_events_and_admin_statistics(self):
        self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'смешная шутка'})[1]['mode'], 'demo')
        self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'абракадабра'})[1]['results'], [])
        self.client.register()
        self.client.call('/api/search', 'POST', {'query': 'спать'})
        original = self.server.provider
        class Broken:
            mode = 'rag'
            def search(self, query):
                raise RuntimeError('Тестовая недоступность RAG')
        self.server.provider = Broken()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'тест ошибки'})[0], 502)
        self.server.provider = original
        self.server.database.create_admin('admin', 'admin-secret')
        admin = Client(self.base)
        admin.call('/api/auth/login', 'POST', {'login': 'admin', 'password': 'admin-secret'})
        stats = admin.call('/api/admin/stats?period=week')[1]
        self.assertEqual((stats['total'], stats['empty'], stats['errors']), (4, 1, 1))
        self.assertEqual(stats['users'], {'guests': 1, 'registered': 1})
        self.assertEqual(sum(d['count'] for d in stats['byDay']), 4)
        memes = admin.call('/api/admin/memes')[1]
        self.assertEqual(sum(m['shows'] for m in memes['top']), 2)
        queries = admin.call('/api/admin/empty-queries')[1]
        self.assertEqual([q['query'] for q in queries], ['абракадабра'])
        admin.call('/api/admin/empty-queries/' + queries[0]['id'], 'DELETE')
        self.assertEqual(admin.call('/api/admin/empty-queries')[1], [])
        self.assertEqual(admin.call('/api/admin/stats?period=day')[1]['empty'], 1)

    def test_validation_csrf_and_static_boundary(self):
        for query in ['', ' ' * 3, 'a' * 1001, 42]:
            self.assertEqual(self.client.call('/api/search', 'POST', {'query': query})[0], 400)
        self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'сон'}, headers={'Content-Type': 'application/json'})[0], 403)
        self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'сон'}, headers={
            'Content-Type': 'application/json', 'X-Requested-With': 'MemeHelper', 'Origin': 'https://example.com'})[0], 403)
        for path in ['/../run.py', '/%2e%2e/run.py', '/.git/config', '/var/memehelper.sqlite3']:
            self.assertEqual(self.client.call(path)[0], 404)
        for path in ['/', '/admin', '/admin/', '/js/api.js', '/images/volk.jpg']:
            self.assertEqual(self.client.call(path)[0], 200)

    def test_plugin_contract_sync_async_and_invalid(self):
        import sys
        import types
        from unittest.mock import patch
        module = types.ModuleType('test_rag_plugin')
        expected = {'results': [], 'answer': 'Нет информации.', 'sources': []}
        module.search = lambda query: dict(expected)
        async def async_search(query):
            return dict(expected)
        module.async_search = async_search
        module.invalid = lambda query: {'results': [{}]}
        with patch.dict(sys.modules, {'test_rag_plugin': module}), patch.dict('os.environ', {'MEME_CATALOG': ''}):
            for target in ['search', 'async_search']:
                provider = SearchProvider('test_rag_plugin:' + target)
                self.assertEqual(provider.search('вопрос'), {**expected, 'mode': 'rag'})
            self.server.provider = SearchProvider('test_rag_plugin:invalid')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.client.call('/api/search', 'POST', {'query': 'тест'})[0], 502)


if __name__ == '__main__':
    unittest.main()
