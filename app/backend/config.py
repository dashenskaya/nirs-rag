"""Загрузка локальной конфигурации проекта из .env."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_env_file(env_path: Path | None = None) -> None:
    """
    Загружает переменные из .env.

    Уже заданные переменные окружения имеют приоритет.
    """

    path = env_path or ROOT / '.env'

    if not path.is_file():
        return

    for line in path.read_text(
        encoding='utf-8-sig'
    ).splitlines():

        line = line.strip()

        if not line or line.startswith('#') or '=' not in line:
            continue

        key, value = line.split('=', 1)

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in ('"', "'")
        ):
            value = value[1:-1]

        if key:
            os.environ.setdefault(key, value)
