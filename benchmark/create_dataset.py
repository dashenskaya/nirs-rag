import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED_PATH = ROOT / "seed" / "memes.json"
OUTPUT_PATH = ROOT / "benchmark" / "dataset.json"


QUESTIONS = [
    # ===== 10 ОБЫЧНЫХ ВОПРОСОВ =====

    {
        "id": "Q01",
        "text": "Покажи постироничные числовые мемы.",
        "trap": False,
        "relevant_ids": [
            "seed-meme-01",
            "seed-meme-02",
            "seed-meme-03"
        ],
        "expected_answer": (
            "В корпусе есть три числовых постироничных мема: "
            "39, 52 и 67."
        )
    },

    {
        "id": "Q02",
        "text": "Дай мне мемов с котами",
        "trap": False,
        "relevant_ids": [
            "seed-meme-09",
            "seed-meme-10",
            "seed-meme-14",
            "seed-meme-27"
        ],
        "expected_answer": (
            "В корпусе есть мемы с растерянными котами, "
            "котом, который пробрался внутрь, кошкой с котёнком, "
            "котом из домового чата и котятами из шутки о краже мемов."
        )
    },

    {
        "id": "Q03",
        "text": (
            "Подбери мемы-реакции, когда я запутался "
            "и не могу понять происходящее или ситуация выглядит странно."
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-09",
            "seed-meme-18",
            "seed-meme-19",
            "seed-meme-21"
        ],
        "expected_answer": (
            "Для растерянности и непонимания подходят "
            "«Глупые коты», «Необычно, зайка», "
            "«Не поняла» и «Почему»."
        )
    },

    {
        "id": "Q04",
        "text": (
            "что отправить человеку, которого постоянно приходится ждать?"
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-11",
            "seed-meme-19",
            "seed-meme-25",
            "seed-meme-30"
        ],
        "expected_answer": (
            "Подходят мемы «Когда», «Работай, чатгпт» "
            "и «Ща ща»."
        )
    },

    {
        "id": "Q05",
        "text": (
            "Какие мемы подойдут, чтобы показать хорошее настроение "
            "и довольство после удачи или небольшой проделки?"
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-12",
            "seed-meme-15",
            "seed-meme-28"
        ],
        "expected_answer": (
            "Подойдут «Пять минут назад», «Напакостничал» "
            "и «Весёлый»."
        )
    },

    {
        "id": "Q06",
        "text": (
            "Найди мемы для разговора о компьютерных технологиях, "
            "микрочипах, написании кода и ChatGPT."
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-14",
            "seed-meme-16",
            "seed-meme-23"
        ],
        "expected_answer": (
            "Подходят «Материнская плата и микрочип», "
            "«Не вайбкодь» и «Работай, чатгпт»."
        )
    },

    {
        "id": "Q07",
        "text": (
            "Подбери мемы для публикаций в онлайн-сообществе: про групповой чат"
            " или что-нибудь для тг-канала или сообщества с мемами"
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-24",
            "seed-meme-27",
            "seed-meme-30"
        ],
        "expected_answer": (
            "Подходят «Как разговорить домовой чат», "
            "«Кража мемов» и «Группа для крутых»."
        )
    },

    {
        "id": "Q08",
        "text": (
            "Дай мне абсурдных мемов"
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-03",
            "seed-meme-05",
            "seed-meme-08",
            "seed-meme-13",
            "seed-meme-29"
        ],
        "expected_answer": (
            "Подходят «Что делать при пожаре», "
            "«Мыться» и «Воздухан»."
        )
    },

    {
        "id": "Q09",
        "text": (
            "Какой мем отправить, когда случилась неприятность, "
            "всё пошло не так или человек грустит"
        ),
        "trap": False,
        "relevant_ids": [
            "seed-meme-04",
            "seed-meme-17",
            "seed-meme-20"
        ],
        "expected_answer": (
            "Для неприятности подходит «Беда», "
            "для невесёлого настроения — «Не весёлый», "
            "для испуга — «Отпусти»."
        )
    },

    {
        "id": "Q10",
        "text": "Покажи мемы с животными",
        "trap": False,
        "relevant_ids": [
            "seed-meme-04",
            "seed-meme-09",
            "seed-meme-10",
            "seed-meme-14",
            "seed-meme-24"
        ],
        "expected_answer": (
            "В корпусе есть мемы с рыбой, котами, кошкой с котёнком "
            "и медведем, а также изображения котов из домового чата "
            "и шутки о краже мемов."
        )
    },

    # ===== 5 ВОПРОСОВ-ЛОВУШЕК =====

    {
        "id": "T01",
        "text": (
            "Какой точный рецепт борща с пропорциями "
            "свёклы, капусты и мяса приведён в базе?"
        ),
        "trap": True,
        "relevant_ids": [],
        "expected_answer": (
            "В корпусе нет рецептов блюд и точных пропорций. "
            "Модель должна отказаться отвечать."
        )
    },

    {
        "id": "T02",
        "text": (
            "Прогноз погоды на завтра "
        ),
        "trap": True,
        "relevant_ids": [],
        "expected_answer": (
            "В корпусе нет прогноза погоды или метеорологических данных. "
            "Модель должна отказаться отвечать."
        )
    },

    {
        "id": "T03",
        "text": (
            "Как настроить VLAN-соединение?"
        ),
        "trap": True,
        "relevant_ids": [],
        "expected_answer": (
            "В корпусе нет реальной инструкции по настройке роутера. "
            "Модель должна отказаться отвечать."
        )
    },

    {
        "id": "T04",
        "text": (
            "В каком сезоне и какой серии сериала "
            "«Ганнибал» умирает гг?"
        ),
        "trap": True,
        "relevant_ids": [],
        "expected_answer": (
            "В корпусе есть упоминание Сэма и Дина, "
            "но отсутствуют сведения о сезонах и сериях. "
            "Модель должна отказаться отвечать."
        )
    },

    {
        "id": "T05",
        "text": (
            "Реши за меня пример: 2+2 ="
        ),
        "trap": True,
        "relevant_ids": [],
        "expected_answer": (
            "В корпусе нет инструкции по управлению каналами "
            "и передаче прав администратора. "
            "Модель должна отказаться отвечать."
        )
    }
]


def build_document(item):
    parts = [
        f"Название: {item['name']}",
        f"Описание: {item['description']}"
    ]

    if item.get("history"):
        parts.append(f"История: {item['history']}")

    if item.get("tags"):
        parts.append("Теги: " + ", ".join(item["tags"]))

    return {
        "id": item["id"],
        "text": "\n".join(parts)
    }


def main():
    if not SEED_PATH.is_file():
        raise SystemExit(f"Не найден файл: {SEED_PATH}")

    seed = json.loads(
        SEED_PATH.read_text(encoding="utf-8-sig")
    )

    if not isinstance(seed, list):
        raise SystemExit("memes.json должен содержать JSON-массив")

    documents = [build_document(item) for item in seed]

    ids = [item["id"] for item in documents]

    if len(documents) != 30:
        raise SystemExit(
            f"Найдено {len(documents)} мемов вместо 30. "
            "Проверь наличие seed-meme-30."
        )

    if len(set(ids)) != 30:
        raise SystemExit("Обнаружены повторяющиеся ID мемов.")

    valid_ids = set(ids)

    if len(QUESTIONS) != 15:
        raise SystemExit("Должно быть ровно 15 вопросов.")

    for question in QUESTIONS:
        relevant = set(question["relevant_ids"])

        if question["trap"] and relevant:
            raise SystemExit(
                f"{question['id']}: у ловушки relevant_ids должен быть пустым."
            )

        if not question["trap"] and len(relevant) < 3:
            raise SystemExit(
                f"{question['id']}: необходимо минимум 3 релевантных документа."
            )

        missing = relevant - valid_ids

        if missing:
            raise SystemExit(
                f"{question['id']}: отсутствуют документы {missing}"
            )

    dataset = {
        "documents": documents,
        "questions": QUESTIONS
    }

    OUTPUT_PATH.write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print("Бенчмарк успешно создан!")
    print(f"Документов: {len(documents)}")
    print("Обычных вопросов: 10")
    print("Вопросов-ловушек: 5")
    print(f"Файл: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
