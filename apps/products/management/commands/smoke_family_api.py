"""Smoke-test API endpoints для ProductFamily без поднятия сервера.

Использует rest_framework APIRequestFactory.
"""
from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand
from rest_framework.test import APIRequestFactory

from apps.api.views import ProductFamilyViewSet
from apps.products.models import ProductFamily


class Command(BaseCommand):
    help = 'Дёргает /api/families/ и /api/families/<id>/ через RequestFactory.'

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--category', default='ssd-nakopiteli')

    def handle(self, *args: Any, **opts: Any) -> None:
        out = self.stdout
        factory = APIRequestFactory()

        out.write(self.style.MIGRATE_HEADING('=== GET /api/families/?category_slug=' + opts['category'] + ' ==='))
        list_view = ProductFamilyViewSet.as_view({'get': 'list'})
        req = factory.get(
            '/api/families/', {'category_slug': opts['category']},
            HTTP_HOST='localhost',
        )
        resp = list_view(req)
        resp.render()
        data = resp.data
        out.write(f'status={resp.status_code}')
        if isinstance(data, dict) and 'results' in data:
            items = data['results']
            out.write(f'count={data.get("count")}, page_size={len(items)}')
        else:
            items = data
            out.write(f'len={len(items)}')

        biggest = max(items, key=lambda f: f.get('variants_count', 0), default=None)
        if not biggest:
            out.write(self.style.WARNING('Нет семей в категории'))
            return

        out.write('\nКрупнейшая семья в категории:')
        out.write(json.dumps(biggest, indent=2, ensure_ascii=False)[:1000])

        family_id = biggest['id']
        out.write(self.style.MIGRATE_HEADING(f'\n=== GET /api/families/{family_id}/ ==='))
        detail_view = ProductFamilyViewSet.as_view({'get': 'retrieve'})
        req = factory.get(f'/api/families/{family_id}/', HTTP_HOST='localhost')
        resp = detail_view(req, pk=family_id)
        resp.render()
        out.write(f'status={resp.status_code}')

        detail = resp.data
        # Печатаем без variants, чтобы было кратко
        slim = {k: v for k, v in detail.items() if k != 'variants'}
        slim['variants_preview'] = []
        for v in (detail.get('variants') or [])[:3]:
            slim['variants_preview'].append({
                'id': v['id'],
                'variant_specs': v.get('variant_specs'),
                'name': (v.get('name') or '')[:80],
                'best_offer': v.get('best_offer'),
            })
        slim['variants_total'] = len(detail.get('variants') or [])
        out.write(json.dumps(slim, indent=2, ensure_ascii=False, default=str))
        out.write(self.style.SUCCESS('\nOK'))
