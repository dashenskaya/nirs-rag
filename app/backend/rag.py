"""Единая точка подключения RAG-провайдера и проверки его ответа."""

import asyncio
import importlib
import inspect
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


class SearchProvider:
    def __init__(self, target=None):
        catalog_path = os.environ.get('MEME_CATALOG')

        self.catalog = (
            json.loads(
                Path(catalog_path).read_text(encoding='utf-8')
            )
            if catalog_path
            else (
                []
                if target
                else json.loads(
                    Path(__file__).with_name(
                        'demo_memes.json'
                    ).read_text(encoding='utf-8')
                )
            )
        )

        self.target = target
        self.function = None
        self.module = None

        if target:
            module_name, function_name = target.split(':', 1)

            self.module = importlib.import_module(module_name)
            self.function = getattr(
                self.module,
                function_name
            )

            if not callable(self.function):
                raise ValueError(
                    'RAG_PROVIDER должен указывать на функцию module:function'
                )

            if callable(
                getattr(self.module, 'list_catalog', None)
            ):
                self.catalog = self.module.list_catalog()

        self._validate_catalog()

    def _validate_catalog(self):
        if not isinstance(self.catalog, list) or any(
            not isinstance(m, dict)
            or not all(
                isinstance(m.get(k), str) and m[k]
                for k in ('id', 'name', 'image')
            )
            for m in self.catalog
        ):
            raise ValueError(
                'Каталог должен быть списком мемов с id, name, image'
            )

    @property
    def mode(self):
        return 'rag' if self.function else 'demo'

    def refresh_catalog(self):
        if self.module and callable(
            getattr(self.module, 'list_catalog', None)
        ):
            self.catalog = self.module.list_catalog()
            self._validate_catalog()

        return self.catalog

    def add_meme(self, **fields):
        if not self.module or not callable(
            getattr(self.module, 'add_meme', None)
        ):
            raise RuntimeError(
                'У текущего RAG-провайдера не реализовано добавление мемов'
            )

        result = self.module.add_meme(**fields)
        self.refresh_catalog()

        return result

    def get_image_url(self, meme_id):
        if not self.module or not callable(
            getattr(
                self.module,
                'get_image_url_for_meme_id',
                None
            )
        ):
            raise LookupError(
                'Текущий RAG-провайдер не поддерживает MinIO-изображения'
            )

        return self.module.get_image_url_for_meme_id(meme_id)

    def search(self, query):
        if self.function:
            result = self.function(query)

            if inspect.isawaitable(result):
                result = asyncio.run(result)

        else:
            q = query.lower().replace('ё', 'е')

            ranked = sorted(
                self.catalog,
                key=lambda m: -sum(
                    k.replace('ё', 'е') in q
                    for k in m['keywords']
                )
            )

            hits = [
                m for m in ranked
                if any(
                    k.replace('ё', 'е') in q
                    for k in m['keywords']
                )
            ][:5]

            result = {
                'results': [
                    {
                        'meme': {
                            k: m[k]
                            for k in (
                                'id', 'name', 'image',
                                'year', 'origin', 'relevance'
                            )
                        },
                        'explanation': (
                            m['meaning']
                            + ' Подходит, потому что '
                            + m['fit'] + '.'
                        ),
                        'suggestion': m['replies'][0],
                    }
                    for m in hits
                ],
                'sources': [
                    {
                        'id': m['id'],
                        'text': m['origin'] + ' ' + m['meaning']
                    }
                    for m in hits
                ],
                'answer': (
                    'Найдены подходящие мемы.'
                    if hits
                    else 'В базе нет подходящих сведений.'
                ),
            }

        validate_response(result)

        return {
            **result,
            'mode': self.mode
        }


    def stream_search(self, query, on_event=None):
        """Потоковый поиск, если его поддерживает подключённый RAG-модуль."""
        streaming_function = (
            getattr(self.module, 'stream_search', None)
            if self.module else None
        )

        if callable(streaming_function):
            result = streaming_function(query, on_event=on_event)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
        else:
            # Совместимость с демо-режимом и сторонними провайдерами без streaming API.
            result = self.search(query)
            if on_event:
                if result.get('answer'):
                    on_event('answer', result['answer'])
                for item in result.get('results', []):
                    on_event('result', item)
            return result

        validate_response(result)
        return {
            **result,
            'mode': self.mode
        }


def validate_response(value):
    """Проверяет новый формат RAG и сохраняет совместимость с демо."""

    if (
        not isinstance(value, dict)
        or not isinstance(value.get('results'), list)
        or len(value['results']) > 5
    ):
        raise ValueError(
            'RAG: ожидается results, список максимум из пяти мемов'
        )

    if (
        not isinstance(value.get('answer'), str)
        or not isinstance(value.get('sources'), list)
    ):
        raise ValueError(
            'RAG: обязательны answer и sources'
        )

    source_ids = set()

    for source in value['sources']:
        if (
            not isinstance(source, dict)
            or not all(
                isinstance(source.get(k), str) and source[k]
                for k in ('id', 'text')
            )
        ):
            raise ValueError(
                'RAG: источник должен содержать id и text'
            )

        if source['id'] in source_ids:
            raise ValueError(
                'RAG: ID источников не должны повторяться'
            )

        source_ids.add(source['id'])

    if value['results'] and not source_ids:
        raise ValueError(
            'RAG: для ответа нужны источники'
        )

    for item in value['results']:

        if (
            not isinstance(item, dict)
            or not all(
                isinstance(item.get(k), str) and item[k]
                for k in ('explanation', 'suggestion')
            )
        ):
            raise ValueError(
                'RAG: неверное объяснение или рекомендация'
            )

        meme = item.get('meme')

        if (
            not isinstance(meme, dict)
            or not all(
                isinstance(meme.get(k), str) and meme[k]
                for k in ('id', 'name', 'image')
            )
        ):
            raise ValueError(
                'RAG: неверные данные мема'
            )

        image = meme['image']
        parsed = urlsplit(image)

        is_http_url = (
            parsed.scheme in ('http', 'https')
            and bool(parsed.netloc)
        )

        is_app_route = image.startswith(
            ('/images/', 'images/', '/api/memes/')
        )

        if not (is_http_url or is_app_route):
            raise ValueError(
                'RAG: изображение должно быть URL '
                'или внутренним маршрутом приложения'
            )

        if 'description' in meme:

            if (
                not isinstance(meme['description'], str)
                or not meme['description'].strip()
            ):
                raise ValueError(
                    'RAG: description должен быть непустой строкой'
                )

        else:
            # Совместимость со старыми демонстрационными мемами.
            if not all(
                isinstance(meme.get(k), str)
                for k in ('origin', 'relevance')
            ) or 'year' not in meme:
                raise ValueError(
                    'RAG: неверное описание мема'
                )

            if (
                meme['year'] is not None
                and not isinstance(meme['year'], (str, int))
            ):
                raise ValueError(
                    'RAG: year должен быть строкой, числом или null'
                )

    json.dumps(value, allow_nan=False)
