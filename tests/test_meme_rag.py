"""Тесты индекса pymorphy3/BM25 без внешнего LLM и MinIO."""

import importlib
import importlib.util
import os
import sys
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch


@unittest.skipUnless(
    importlib.util.find_spec('pymorphy3'),
    'Установите зависимости: pip install -r requirements.txt'
)
class MemeRagTests(unittest.TestCase):

    def setUp(self):

        self.temp = tempfile.TemporaryDirectory()

        self.db_path = (
            Path(self.temp.name)
            / 'meme-rag-test.sqlite3'
        )

        self.env = patch.dict(
            os.environ,
            {'MEME_DB_PATH': str(self.db_path)}
        )

        self.env.start()

        # Модуль читает MEME_DB_PATH при импорте.
        sys.modules.pop(
            'app.backend.meme_rag',
            None
        )

        self.rag = importlib.import_module(
            'app.backend.meme_rag'
        )

        with self.rag._connect() as db:

            db.execute('DELETE FROM meme_terms')
            db.execute('DELETE FROM meme_catalog')

            db.execute(
                'UPDATE meme_index_meta '
                'SET version=version+1 WHERE id=1'
            )

        self.rag._INDEX_CACHE = None

    def tearDown(self):

        sys.modules.pop(
            'app.backend.meme_rag',
            None
        )

        self.env.stop()
        self.temp.cleanup()

    def test_add_meme_creates_normalized_tokens_and_searches_it(self):

        self.rag.add_meme(
            meme_id='meme-new',
            name='Уставший кот',
            description='Кот устал после долгого рабочего дня',
            history='',
            image_key='memes/cat.jpg',
        )

        hits = self.rag.retrieve_candidates('Коты')

        self.assertTrue(hits)

        self.assertEqual(
            hits[0]['meme']['id'],
            'meme-new'
        )

        with self.rag._connect() as db:

            tokens = {
                row['token']
                for row in db.execute(
                    'SELECT token FROM meme_terms WHERE meme_id=?',
                    ('meme-new',)
                )
            }

        self.assertIn('кот', tokens)
        self.assertIn('устать', tokens)

    def test_tag_aliases_match_canonical_tags(self):
        self.rag.add_meme(
            'absurd-meme',
            'Странный мем',
            'Нелепая ситуация',
            '',
            'm/absurd.jpg',
            tags=['абсурд']
        )
        self.rag.add_meme(
            'ordinary-meme',
            'Обычный мем',
            'Спокойная ситуация',
            '',
            'm/ordinary.jpg',
            tags=['реакция']
        )

        hits = self.rag.retrieve_candidates('Покажи абсурдный мем')

        self.assertEqual(
            [hit['meme']['id'] for hit in hits],
            ['absurd-meme']
        )

    def test_history_field_has_lower_weight_than_name_and_description(self):

        self.rag.add_meme(
            'name-hit',
            'кот',
            'нейтральное описание',
            '',
            'm/name.jpg'
        )

        self.rag.add_meme(
            'description-hit',
            'нейтральное имя',
            'кот',
            '',
            'm/description.jpg'
        )

        self.rag.add_meme(
            'history-hit',
            'другое имя',
            'другое описание',
            'кот',
            'm/history.jpg'
        )

        hits = self.rag.retrieve_candidates(
            'кот',
            top_k=3
        )

        scores = {
            hit['meme']['id']: hit['score']
            for hit in hits
        }

        self.assertGreater(
            scores['name-hit'],
            scores['history-hit']
        )

        self.assertGreater(
            scores['description-hit'],
            scores['history-hit']
        )

    def test_non_url_image_key_only(self):

        with self.assertRaises(ValueError):

            self.rag.add_meme(
                'bad',
                'Название',
                'Описание',
                '',
                'https://site.example/pic.jpg'
            )


if __name__ == '__main__':
    unittest.main()
