"""Точка подключения RAG. Демо используется только для проверки бэкенда."""
import asyncio
import importlib
import inspect
import json
import os
from pathlib import Path


class SearchProvider:
    def __init__(self, target=None):
        catalog_path = os.environ.get('MEME_CATALOG')
        self.catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8')) if catalog_path else (
            [] if target else json.loads(Path(__file__).with_name('demo_memes.json').read_text(encoding='utf-8')))
        if not isinstance(self.catalog, list) or any(
            not isinstance(m, dict) or not all(isinstance(m.get(k), str) and m[k] for k in ('id', 'name', 'image'))
            for m in self.catalog
        ):
            raise ValueError('MEME_CATALOG: ожидается список мемов с id, name, image')
        self.target = target
        self.function = None
        if target:
            module, name = target.split(':', 1)
            self.function = getattr(importlib.import_module(module), name)
            if not callable(self.function):
                raise ValueError('RAG_PROVIDER должен указывать на функцию module:function')

    @property
    def mode(self):
        return 'rag' if self.function else 'demo'

    def search(self, query):
        if self.function:
            result = self.function(query)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
        else:
            q = query.lower().replace('ё', 'е')
            ranked = sorted(self.catalog, key=lambda m: -sum(k.replace('ё', 'е') in q for k in m['keywords']))
            hits = [m for m in ranked if any(k.replace('ё', 'е') in q for k in m['keywords'])][:5]
            result = {
                'results': [{
                    'meme': {k: m[k] for k in ('id', 'name', 'image', 'year', 'origin', 'relevance')},
                    'explanation': m['meaning'] + ' Подходит, потому что ' + m['fit'] + '.',
                    'suggestion': m['replies'][0],
                } for m in hits],
                'sources': [{'id': m['id'], 'text': m['origin'] + ' ' + m['meaning']} for m in hits],
                'answer': 'Найдены подходящие мемы.' if hits else 'В базе нет подходящих сведений.',
            }
        validate_response(result)
        return {**result, 'mode': self.mode}


def validate_response(value):
    """Ошибка провайдера должна стать 502, а не сломать отрисовку сайта."""
    if not isinstance(value, dict) or not isinstance(value.get('results'), list) or len(value['results']) > 5:
        raise ValueError('RAG: ожидается results, список максимум из пяти мемов')
    if not isinstance(value.get('answer'), str) or not isinstance(value.get('sources'), list):
        raise ValueError('RAG: обязательны answer и sources')
    source_ids = set()
    for source in value['sources']:
        if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source[k] for k in ('id', 'text')):
            raise ValueError('RAG: источник должен содержать id и text')
        if source['id'] in source_ids:
            raise ValueError('RAG: ID источников не должны повторяться')
        source_ids.add(source['id'])
    if value['results'] and not source_ids:
        raise ValueError('RAG: для ответа нужны источники')
    for item in value['results']:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ('explanation', 'suggestion')):
            raise ValueError('RAG: неверное объяснение или рекомендация')
        meme = item.get('meme')
        if not isinstance(meme, dict) or not all(isinstance(meme.get(k), str) for k in ('id', 'name', 'image', 'origin', 'relevance')):
            raise ValueError('RAG: неверные данные мема')
        if not meme['id'] or 'year' not in meme:
            raise ValueError('RAG: нужны id и year (допускается null)')
        image = meme['image']
        if not (image.startswith('/images/') or image.startswith('images/') or image.startswith('https://')):
            raise ValueError('RAG: изображение должно быть в images/ или по HTTPS')
    json.dumps(value, allow_nan=False)
