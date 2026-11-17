import unittest
from benchmark.run import evaluate


class BenchmarkTests(unittest.TestCase):
    def test_metrics_and_traps(self):
        dataset = {
            'documents': [{'id': f'D{i:02}', 'text': f'Документ {i}'} for i in range(1, 31)],
            'questions': [{'id': f'Q{i:02}', 'text': 'вопрос', 'trap': i > 10,
                           'relevant_ids': ['D01', 'D02', 'D03'] if i <= 10 else [],
                           'expected_answer': 'эталон'} for i in range(1, 16)],
        }
        class Provider:
            mode = 'rag'
            def search(self, query):
                return {'answer': 'пример', 'results': [], 'sources': [{'id': x} for x in ['D04', 'D01', 'D02']]}
        review = {q['id']: True for q in dataset['questions']}
        result = evaluate(dataset, Provider(), 3, review)
        self.assertAlmostEqual(result['metrics']['recall_at_k'], 2/3)
        self.assertEqual(result['metrics']['mrr_at_k'], .5)
        self.assertEqual(result['metrics']['accuracy'], 1)
        self.assertEqual(result['metrics']['correct_rejection_rate'], 1)
        self.assertIsNone(evaluate(dataset, Provider())['metrics']['accuracy'])
        dataset['documents'].pop()
        with self.assertRaises(ValueError):
            evaluate(dataset, Provider())
