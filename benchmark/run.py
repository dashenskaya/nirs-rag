"""Бенчмарк реального RAG; запуск из корня: python -m benchmark.run --help."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import mean

from app.backend.rag import SearchProvider
from app.backend.config import load_env_file


def evaluate(dataset, provider, k=3, review=None):
    documents, questions = dataset['documents'], dataset['questions']
    ids = [d['id'] for d in documents]
    if len(ids) != 30 or len(set(ids)) != 30 or any(not isinstance(d.get('text'), str) or not d['text'].strip() for d in documents):
        raise ValueError('Нужны 30 уникальных документов с id и непустым text')
    normal = [q for q in questions if not q.get('trap')]
    traps = [q for q in questions if q.get('trap')]
    qids = [q['id'] for q in questions]
    if len(normal) != 10 or len(traps) != 5 or len(set(qids)) != 15:
        raise ValueError('Нужны 10 обычных вопросов и 5 ловушек с уникальными ID')
    if k < 1:
        raise ValueError('k должно быть положительным')
    if review is not None and (set(review) != set(qids) or any(type(v) is not bool for v in review.values())):
        raise ValueError('Ручная разметка: объект со всеми 15 ID вопросов и значениями true/false')
    results, recalls, reciprocal_ranks = [], [], []
    for question in questions:
        relevant = set(question['relevant_ids'])
        if not isinstance(question.get('expected_answer'), str) or not question['expected_answer'].strip():
            raise ValueError('У каждого вопроса нужен expected_answer, включая отказ для ловушки')
        if not isinstance(question.get('text'), str) or not question['text'].strip():
            raise ValueError('У каждого вопроса нужен text')
        if not relevant.issubset(ids) or (question.get('trap') and relevant) or (not question.get('trap') and len(relevant) < 3):
            raise ValueError('Обычный вопрос: минимум 3 релевантных ID; ловушка: пустой relevant_ids')
        print(
            f"\n[BENCHMARK] {question['id']}: "
            f"{question['text']}",
            flush=True
        )
        response = provider.search(question['text'])
        ranked = list(dict.fromkeys(s['id'] for s in response['sources']))[:k]
        if any(doc_id not in ids for doc_id in ranked):
            raise ValueError('RAG вернул источник, которого нет в корпусе бенчмарка')
        row = {'id': question['id'], 'question': question['text'], 'trap': bool(question.get('trap')),
               'expected_answer': question['expected_answer'], 'relevant_ids': sorted(relevant),
               'retrieved_ids': ranked, 'response': response}
        if not question.get('trap'):
            recall = len(relevant.intersection(ranked)) / len(relevant)
            rr = next((1 / (i + 1) for i, doc in enumerate(ranked) if doc in relevant), 0)
            recalls.append(recall)
            reciprocal_ranks.append(rr)
            row.update(recall=recall, reciprocal_rank=rr)
        if review is not None:
            row['manually_correct'] = review[question['id']]
        results.append(row)
    return {'mode': provider.mode, 'k': k, 'mrr_depth': k,
            'metrics': {'recall_at_k': mean(recalls), 'mrr_at_k': mean(reciprocal_ranks),
                        'accuracy': mean(review[q['id']] for q in normal) if review is not None else None,
                        'correct_rejection_rate': mean(review[q['id']] for q in traps) if review is not None else None},
            'review_status': 'complete' if review is not None else 'Нужна ручная оценка ответов и отказов',
            'results': results}


def main():
    load_env_file()
    parser = argparse.ArgumentParser(description='Проверка RAG по требованиям контрольной точки')
    parser.add_argument('dataset', type=Path)
    parser.add_argument('--k', type=int, default=3)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path, default=Path('benchmark/results.local.json'))
    args = parser.parse_args()
    if not os.environ.get('RAG_PROVIDER'):
        parser.error('Сначала подключите настоящий RAG через RAG_PROVIDER. Демо не является учебным RAG.')
    try:
        provider = SearchProvider(os.environ['RAG_PROVIDER'])
        dataset = json.loads(args.dataset.read_text(encoding='utf-8'))
        fingerprint = hashlib.sha256(json.dumps(dataset, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
        review = json.loads(args.review.read_text(encoding='utf-8')) if args.review else None
        if review is None:
            result = evaluate(dataset, provider, args.k)
            result['dataset_sha256'] = fingerprint
            result['provider'] = os.environ['RAG_PROVIDER']
        else:
            # Оценка относится к сохранённым ответам: повторный вызов LLM их изменил бы.
            result = json.loads(args.output.read_text(encoding='utf-8'))
            if result.get('dataset_sha256') != fingerprint:
                raise ValueError('Корпус или вопросы изменились после сохранённого прогона')
            rows = result['results']
            if set(review) != {q['id'] for q in rows} or any(type(v) is not bool for v in review.values()):
                raise ValueError('Нужны оценки true/false для всех 15 сохранённых вопросов')
            original = {q['id']: q for q in dataset['questions']}
            if set(original) != set(review) or any(
                original[r['id']]['text'] != r['question'] or original[r['id']]['expected_answer'] != r['expected_answer']
                or sorted(original[r['id']]['relevant_ids']) != r['relevant_ids']
                or bool(original[r['id']].get('trap')) != r['trap'] for r in rows
            ):
                raise ValueError('Набор вопросов отличается от сохранённого прогона')
            for row in rows:
                row['manually_correct'] = review[row['id']]
            result['metrics']['accuracy'] = mean(r['manually_correct'] for r in rows if not r['trap'])
            result['metrics']['correct_rejection_rate'] = mean(r['manually_correct'] for r in rows if r['trap'])
            result['review_status'] = 'complete'
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result['metrics'], ensure_ascii=False, indent=2))
    print(result['review_status'])


if __name__ == '__main__':
    main()
