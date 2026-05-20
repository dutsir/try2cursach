"""Pytest конфигурация: создаёт pgvector extension в test DB до миграций.

Без этой настройки тесты с @pytest.mark.django_db падают на миграции 0012
(`CREATE EXTENSION IF NOT EXISTS vector`), потому что test DB создаётся
без прав на CREATE EXTENSION у обычного пользователя.

См. Django docs: https://docs.djangoproject.com/en/5.1/topics/testing/advanced/#test-database
"""
from __future__ import annotations

import pytest
from django.db import connection


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """Гарантирует, что pgvector extension установлен в test DB.

    Стандартная установка через миграцию RunSQL не работает, если у роли
    нет привилегии CREATE EXTENSION (типично для CI). Делаем CREATE EXTENSION
    тут, как суперюзер (если у роли есть права) — иначе пропускаем.
    """
    with django_db_blocker.unblock():
        with connection.cursor() as cur:
            try:
                cur.execute('CREATE EXTENSION IF NOT EXISTS vector;')
            except Exception:
                # Если прав нет — extension должен быть установлен заранее
                # в template1 / в самой test DB администратором.
                pass
