from __future__ import annotations

from django.db import migrations
from django.utils.text import slugify


GROUPS: dict[str, list[str]] = {
    'Компьютеры и ноутбуки': [
        'Ноутбуки',
        'Моноблоки',
        'Персональные компьютеры',
        'Микрокомпьютеры',
    ],
    'Комплектующие ПК': [
        'Видеокарты',
        'Процессоры',
        'Материнские платы',
        'Оперативная память',
        'Блоки питания',
        'Корпуса',
        'Охлаждение для серверных процессоров',
        'Звуковые карты',
        'Карты видеозахвата',
        'Платы расширения',
        'Оптические приводы',
    ],
    'Накопители': [
        'SSD-накопители',
        'Жёсткие диски 3.5" (HDD)',
        'Внешние SSD',
        'Внешние оптические приводы',
        'Адаптеры для накопителей',
        'Корзины для накопителей',
    ],
    'Мониторы': [
        'Мониторы',
        'Многофункциональные панели',
    ],
    'Периферия': [
        'Мыши',
        'Клавиатуры',
    ],
    'Сетевое оборудование': [
        'Сетевые карты',
        'Сетевые хранилища',
    ],
    'Серверное оборудование': [
        'Серверные процессоры',
        'Серверные материнские платы',
        'Серверная память',
        'Серверные SSD',
        'Серверные корпуса',
        'Серверные блоки питания',
        'Серверные направляющие',
        'Серверные операционные системы',
        'Серверные кабели и переходники',
        'Аксессуары для серверных корпусов',
        'Аксессуары для материнских плат',
    ],
}


def _find_leaf(Category, name: str):
    obj = Category.objects.filter(name=name).first()
    if obj is not None:
        return obj

    s = slugify(name, allow_unicode=True)
    return Category.objects.filter(slug=s).first()


def create_groups(apps, schema_editor):
    Category = apps.get_model('products', 'Category')

    for group_name, leaves in GROUPS.items():
        group, _created = Category.objects.get_or_create(
            slug=slugify(group_name, allow_unicode=True),
            defaults={'name': group_name, 'is_active': True, 'parent': None},
        )

        if group.parent_id is not None:
            group.parent = None
            group.save(update_fields=['parent'])

        for leaf_name in leaves:
            leaf = _find_leaf(Category, leaf_name)
            if leaf is None:
                continue

            if leaf.parent_id is None:
                leaf.parent = group
                leaf.save(update_fields=['parent'])


def remove_groups(apps, schema_editor):
    Category = apps.get_model('products', 'Category')

    group_slugs = [slugify(name, allow_unicode=True) for name in GROUPS]
    groups = Category.objects.filter(slug__in=group_slugs, parent__isnull=True)
    Category.objects.filter(parent__in=groups).update(parent=None)
    groups.filter(children__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0006_category_parent'),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]
