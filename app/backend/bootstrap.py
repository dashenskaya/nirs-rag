"""Инициализация SQLite, MinIO и демонстрационных мемов."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time

from pathlib import Path

import boto3

from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from .config import ROOT, load_env_file
from .migrations import apply_migrations


SEED_MANIFEST = ROOT / 'seed' / 'memes.json'

SEED_IMAGES = ROOT / 'seed_images'

LEGACY_IMAGES = ROOT / 'app' / 'MemeHelper' / 'images'


def _minio_settings():

    endpoint = os.environ.get(
        'MINIO_ENDPOINT',
        'http://127.0.0.1:9000'
    ).strip()

    access_key = os.environ.get(
        'MINIO_ACCESS_KEY',
        ''
    ).strip()

    secret_key = os.environ.get(
        'MINIO_SECRET_KEY',
        ''
    ).strip()

    bucket = os.environ.get(
        'MINIO_BUCKET',
        'meme-images'
    ).strip()

    if not all((
        endpoint,
        access_key,
        secret_key,
        bucket
    )):
        raise RuntimeError(
            'Заполните настройки MinIO в .env'
        )

    return endpoint, access_key, secret_key, bucket


def _make_minio_client():

    endpoint, access_key, secret_key, _ = (
        _minio_settings()
    )

    return boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.environ.get(
            'MINIO_REGION',
            'us-east-1'
        ),
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}
        ),
    )


def _ensure_bucket(client, bucket):

    """Создаёт приватный bucket только при его отсутствии."""

    last_error = None

    for attempt in range(45):

        try:

            try:

                client.head_bucket(
                    Bucket=bucket
                )

                print(
                    f'[MinIO] Bucket {bucket!r} уже существует.'
                )

                return

            except ClientError as error:

                code = str(
                    error.response.get(
                        'Error', {}
                    ).get('Code', '')
                )

                status = error.response.get(
                    'ResponseMetadata', {}
                ).get('HTTPStatusCode')

                if code not in {
                    '404',
                    'NoSuchBucket',
                    'NotFound'
                } and status != 404:
                    raise

                try:

                    client.create_bucket(
                        Bucket=bucket
                    )

                    print(
                        f'[MinIO] Создан bucket {bucket!r}.'
                    )

                    return

                except ClientError as create_error:

                    create_code = str(
                        create_error.response.get(
                            'Error', {}
                        ).get('Code', '')
                    )

                    if create_code in {
                        'BucketAlreadyOwnedByYou',
                        'BucketAlreadyExists'
                    }:
                        return

                    raise

        except (BotoCoreError, OSError) as error:

            last_error = error

        except ClientError as error:

            last_error = error

            code = str(
                error.response.get(
                    'Error', {}
                ).get('Code', '')
            )

            status = error.response.get(
                'ResponseMetadata', {}
            ).get('HTTPStatusCode')

            if code in {
                'AccessDenied',
                'InvalidAccessKeyId',
                'SignatureDoesNotMatch'
            } or status == 403:

                raise RuntimeError(
                    'MinIO не принимает учётные данные из .env.'
                ) from error

        if attempt < 44:
            time.sleep(2)

    raise RuntimeError(
        'MinIO не стал доступен за 90 секунд.'
    ) from last_error


def _sha256(path: Path):

    digest = hashlib.sha256()

    with path.open('rb') as file:

        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b''
        ):

            digest.update(chunk)

    return digest.hexdigest()


def _upload_file(
    client,
    bucket,
    source: Path,
    object_key
):

    """Загружает изображение, если его ещё нет или оно изменилось."""

    digest = _sha256(source)

    try:

        remote = client.head_object(
            Bucket=bucket,
            Key=object_key
        )

        remote_hash = remote.get(
            'Metadata', {}
        ).get('sha256')

        if remote_hash == digest:
            return False

    except ClientError as error:

        code = str(
            error.response.get(
                'Error', {}
            ).get('Code', '')
        )

        status = error.response.get(
            'ResponseMetadata', {}
        ).get('HTTPStatusCode')

        if code not in {
            '404',
            'NoSuchKey',
            'NotFound'
        } and status != 404:
            raise

    content_type = (
        mimetypes.guess_type(source.name)[0]
        or 'application/octet-stream'
    )

    client.upload_file(
        str(source),
        bucket,
        object_key,
        ExtraArgs={
            'ContentType': content_type,
            'Metadata': {
                'sha256': digest
            },
        },
    )

    return True


def _load_seed_manifest():
    if not SEED_MANIFEST.is_file():
        raise RuntimeError(
            f'Не найден файл {SEED_MANIFEST}'
        )

    data = json.loads(
        SEED_MANIFEST.read_text(encoding='utf-8')
    )

    if not isinstance(data, list) or not data:
        raise RuntimeError(
            'seed/memes.json должен содержать непустой список записей.'
        )

    if any(
        not isinstance(item, dict)
        or not isinstance(item.get('id'), str)
        or not item['id'].strip()
        for item in data
    ):
        raise RuntimeError(
            'Каждая запись должна иметь непустой строковый id.'
        )

    ids = [item['id'] for item in data]

    if len(ids) != len(set(ids)):
        raise RuntimeError(
            'В seed/memes.json обнаружены повторяющиеся id.'
        )

    return data


def initialize_demo_data():

    """
    Создаёт bucket, загружает фотографии
    и добавляет соответствующие записи в SQLite.
    """

    _, _, _, bucket = _minio_settings()

    client = _make_minio_client()

    _ensure_bucket(
        client,
        bucket
    )

    # Импортируем после загрузки конфигурации и миграций.
    from . import meme_rag

    uploaded = 0
    seeded = 0
    missing = 0

    # Перенос старых демонстрационных изображений.

    for filename in (
        'okno.jpg',
        'volk.jpg'
    ):

        source = LEGACY_IMAGES / filename

        if source.is_file():

            uploaded += int(
                _upload_file(
                    client,
                    bucket,
                    source,
                    f'images/{filename}'
                )
            )

    # Загрузка 25 демонстрационных изображений.

    seed_items = _load_seed_manifest()

    for item in seed_items:

        if not isinstance(item, dict):

            raise RuntimeError(
                'Каждая запись должна быть JSON-объектом.'
            )

        image_file = item.get(
            'image_file'
        )

        if (
            not isinstance(image_file, str)
            or not image_file
            or Path(image_file).name != image_file
        ):

            raise RuntimeError(
                'image_file должен содержать только имя файла.'
            )

        source = SEED_IMAGES / image_file

        if not source.is_file():

            missing += 1
            continue

        meme_id = item.get('id')
        name = item.get('name')
        description = item.get('description')
        history = item.get('history', '')
        tags = item.get('tags', [])

        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise RuntimeError(f'tags для {image_file} должны быть списком непустых строк.')

        image_key = f'seed/{image_file}'

        if not all(
            isinstance(value, str) and value.strip()
            for value in (
                meme_id,
                name,
                description
            )
        ):

            raise RuntimeError(
                f'Не заполнены данные для {image_file}.'
            )

        if not isinstance(history, str):

            raise RuntimeError(
                f'history для {image_file} должна быть строкой.'
            )

        uploaded += int(
            _upload_file(
                client,
                bucket,
                source,
                image_key
            )
        )

        meme_rag.add_meme(
            meme_id=meme_id,
            name=name,
            description=description,
            history=history,
            image_key=image_key,
            tags=tags,
        )

        seeded += 1

    print(
        f'[MinIO] Загружено/обновлено объектов: {uploaded}.'
    )

    print(
        f'[SQLite] Добавлено/обновлено мемов: {seeded}/{len(seed_items)}.'
    )

    if missing:

        print(
            f'[ВНИМАНИЕ] Отсутствует фотографий: {missing}/{len(seed_items)}.'
        )

        print(
            'Поместите фотографии в seed_images '
            'и повторите запуск.'
        )

    return uploaded, seeded, missing


def main():

    load_env_file()

    db_path = Path(
        os.environ.get(
            'MEME_DB_PATH',
            ROOT / 'var' / 'memehelper.sqlite3'
        )
    ).resolve()

    os.environ['MEME_DB_PATH'] = str(db_path)

    applied = apply_migrations(db_path)

    if applied:

        print(
            '[SQLite] Применены миграции: '
            + ', '.join(applied)
        )

    else:

        print(
            '[SQLite] Миграции уже актуальны.'
        )

    initialize_demo_data()


if __name__ == '__main__':
    main()
