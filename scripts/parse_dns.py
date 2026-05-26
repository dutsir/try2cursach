#!/usr/bin/env python
"""
Точечный запуск парсинга DNS-категорий из shell.

Использование:
    # Список всех DNS-категорий с ID
    python scripts/parse_dns.py --list

    # Запуск одной категории (по slug или ID)
    python scripts/parse_dns.py ssd-nakopiteli
    python scripts/parse_dns.py 5

    # Несколько категорий цепочкой с паузами 180 сек
    python scripts/parse_dns.py klaviatury myshi korpusa --chain

    # Несколько параллельно (ОПАСНО при concurrency>1 — может быть OOM)
    python scripts/parse_dns.py klaviatury myshi --parallel

    # Статус задачи
    python scripts/parse_dns.py --status c2573efc-79f2-414c-86d3-1504453fe0bb
"""
import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description='Точечный запуск парсинга DNS')
    parser.add_argument('categories', nargs='*', help='slug или ID категорий')
    parser.add_argument('--list', action='store_true', help='показать все DNS категории')
    parser.add_argument('--chain', action='store_true', help='запустить цепочкой с паузами')
    parser.add_argument('--parallel', action='store_true', help='запустить параллельно')
    parser.add_argument('--pause', type=int, default=180, help='пауза между категориями (для --chain)')
    parser.add_argument('--status', help='проверить статус задачи по Task ID')
    args = parser.parse_args()

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import django
    django.setup()

    from apps.products.models import Category

    if args.list:
        print(f"{'ID':<5} {'SLUG':<35} {'NAME':<30} {'DNS':<10}")
        print('-' * 90)
        for c in Category.objects.filter(is_active=True).order_by('slug'):
            l = c.listings.filter(source='dns').first()
            state = '✓ active' if (l and l.is_active) else ('✗ inactive' if l else '— нет')
            print(f"{c.id:<5} {c.slug[:34]:<35} {c.name[:29]:<30} {state}")
        return 0

    if args.status:
        from celery.result import AsyncResult
        r = AsyncResult(args.status)
        print(f"State : {r.state}")
        print(f"Result: {r.result}")
        return 0

    if not args.categories:
        parser.print_help()
        return 1

    cats = []
    for ident in args.categories:
        try:
            c = Category.objects.get(id=int(ident)) if ident.isdigit() else Category.objects.get(slug=ident)
            cats.append(c)
        except Category.DoesNotExist:
            print(f"⚠ Не найдена: {ident}")
            return 1

    from apps.prices.tasks import task_parse_category, task_pause_between_dns_categories

    if args.chain and len(cats) > 1:
        from celery import chain
        links = []
        for i, c in enumerate(cats):
            links.append(task_parse_category.si(c.id))
            if i < len(cats) - 1:
                links.append(task_pause_between_dns_categories.si(args.pause))
        result = chain(*links).apply_async()
        print(f"✅ Цепочка из {len(cats)} категорий запущена")
        for c in cats:
            print(f"   • {c.slug} (id={c.id})")
        print(f"Task ID: {result.id}")
    else:
        for c in cats:
            r = task_parse_category.delay(c.id)
            print(f"✅ {c.slug:30} | Task: {r.id}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
