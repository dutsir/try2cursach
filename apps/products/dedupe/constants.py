from __future__ import annotations

from django.conf import settings


AUTO_MERGE_THRESHOLD: float = float(
    getattr(settings, 'DEDUP_AUTO_MERGE_THRESHOLD', 0.85),
)


REVIEW_THRESHOLD: float = float(
    getattr(settings, 'DEDUP_REVIEW_THRESHOLD', 0.65),
)


WEIGHTS: dict[str, float] = {
    'brand': 0.35,
    'model_code': 0.30,
    'screen_in': 0.15,
    'ram_gb': 0.10,
    'storage_gb': 0.10,
    'cpu_family': 0.07,
    'gpu_family': 0.05,
}


NAME_DICE_WEIGHT: float = 0.20


SOFT_CONFLICT_PENALTY: dict[str, float] = {
    'storage_gb': 0.40,
    'screen_in': 0.40,
    'color': 0.10,
}


# ВАЖНО: HARD_REJECT_KEYS — поля, расхождение которых ЗАПРЕЩАЕТ матчинг.
# Раньше тут были ram_gb, storage_gb, screen_in — но это варианты!
# Kingston FURY 8GB и 16GB должны быть в одной family как варианты,
# а не отвергаться по ram_gb.
#
# Логика умнее: variant-поля учитываются в hard_reject через
# VARIANT_SPEC_KEYS_BY_CATEGORY — если для категории это variant,
# то расхождение ОК; иначе — conflict.
HARD_REJECT_KEYS: tuple[str, ...] = (
    'model_code',
)


TRUSTED_MPN_SOURCES: frozenset[str] = frozenset({'dns', 'citilink'})


WEAK_SOURCES: frozenset[str] = frozenset({'ozon'})


BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    'apple': ('apple', 'эппл', 'эпл'),
    'asus': ('asus', 'асус'),
    'acer': ('acer', 'эйсер'),
    'lenovo': ('lenovo', 'леново'),
    'huawei': ('huawei', 'хуавей', 'хуавэй'),
    'honor': ('honor', 'хонор'),
    'dell': ('dell', 'делл'),
    'hp': ('hp', 'hewlett packard', 'hewlett-packard', 'хьюлетт-паккард'),
    'msi': ('msi',),
    'gigabyte': ('gigabyte',),
    'samsung': ('samsung', 'самсунг'),
    'lg': ('lg', 'эл джи', 'элджи'),
    'xiaomi': ('xiaomi', 'сяоми', 'сяоми'),
    'redmi': ('redmi',),
    'kingston': ('kingston',),
    'crucial': ('crucial',),
    'western digital': ('western digital', 'wd', 'wd_black', 'wd black'),
    'seagate': ('seagate',),
    'sandisk': ('sandisk',),
    'corsair': ('corsair',),
    'gskill': ('g.skill', 'gskill', 'g-skill'),
    'thermaltake': ('thermaltake',),
    'nzxt': ('nzxt',),
    'beelink': ('beelink',),
    'irbis': ('irbis', 'ирбис'),
    'tecno': ('tecno', 'текно'),
    'infinix': ('infinix',),
    'realme': ('realme',),
    'dexp': ('dexp', 'дексп'),
    'digma': ('digma', 'дигма'),
    'haier': ('haier', 'хайер'),
    'hiper': ('hiper', 'хайпер'),
    'logitech': ('logitech', 'логитек'),
    'razer': ('razer',),
    'intel': ('intel', 'интел'),
    'amd': ('amd',),
    'nvidia': ('nvidia', 'нвидиа'),
    'palit': ('palit', 'палит'),
    'gainward': ('gainward',),
    'sapphire': ('sapphire',),
    'colorful': ('colorful',),
    'inno3d': ('inno3d',),
    'zotac': ('zotac',),
    'aerocool': ('aerocool',),
    'deepcool': ('deepcool', 'deep cool'),
    'cougar': ('cougar',),
    'chieftec': ('chieftec',),
    'exegate': ('exegate', 'экзегейт'),
    'fractal design': ('fractal design', 'fractal-design'),
    'asrock': ('asrock', 'asrock'),
    'lian li': ('lian li', 'lian-li', 'lianli'),
    'be quiet!': ('be quiet!', 'be quiet', 'bequiet'),
}


CPU_FAMILIES: tuple[str, ...] = (
    'core ultra 9', 'core ultra 7', 'core ultra 5', 'core ultra 3',
    'core i9', 'core i7', 'core i5', 'core i3',
    'core 9', 'core 7', 'core 5', 'core 3',
    'ryzen 9', 'ryzen 7', 'ryzen 5', 'ryzen 3',
    'xeon', 'pentium', 'celeron',
    'apple m4', 'apple m3', 'apple m2', 'apple m1',
)

GPU_FAMILIES: tuple[str, ...] = (
    'rtx 5090', 'rtx 5080', 'rtx 5070', 'rtx 5060',
    'rtx 4090', 'rtx 4080', 'rtx 4070', 'rtx 4060', 'rtx 4050',
    'rtx 3090', 'rtx 3080', 'rtx 3070', 'rtx 3060', 'rtx 3050',
    'rtx 2080', 'rtx 2070', 'rtx 2060',
    'gtx 1660', 'gtx 1650',
    'rx 9070', 'rx 7900', 'rx 7800', 'rx 7700', 'rx 7600',
    'rx 6800', 'rx 6700', 'rx 6600',
    'arc a770', 'arc a750', 'arc b580',
    'iris xe', 'uhd graphics', 'radeon graphics',
)


RE_BRACKET_MPN: str = r'\[([A-Za-z0-9][A-Za-z0-9\-_/.]{3,})\]'


RE_FREE_MPN: str = r'\b([A-Z]{1,4}\d{2,}[A-Z0-9\-/_]{0,}|\d{2,}[A-Z]{1,4}\d{2,}[A-Z0-9\-/_]{0,})\b'


COLORS: tuple[str, ...] = (
    'черный', 'чёрный', 'black', 'white', 'белый', 'silver', 'серебристый', 'серый',
    'grey', 'gray', 'space gray', 'space grey', 'gold', 'золотой', 'розовый', 'pink',
    'красный', 'red', 'синий', 'blue', 'зеленый', 'зелёный', 'green',
)


# Ключи specs, по которым внутри одной категории товары считаются ВАРИАНТАМИ
# одного семейства, а не разными товарами. Всё, чего нет в этом наборе для
# данной категории, попадает в common_specs (общие для семьи).
# Slug категории берётся из Category.slug (см. seed_categories.BUILTIN_CATEGORIES).
VARIANT_SPEC_KEYS_BY_CATEGORY: dict[str, frozenset[str]] = {
    # SSD/HDD/серверные накопители: одна модель — разные ёмкости
    'ssd-nakopiteli': frozenset({'storage_gb'}),
    'zhestkie-diski-35': frozenset({'storage_gb'}),
    'servernye-nakopiteli': frozenset({'storage_gb'}),
    'vneshnie-ssd': frozenset({'storage_gb'}),
    # Ноутбуки/моноблоки/готовые ПК/микрокомпьютеры: одна линейка модели —
    # разные конфиги RAM/SSD. CPU/GPU НЕ варианты — это разные SKU сборщика.
    'noutbuki': frozenset({'ram_gb', 'storage_gb'}),
    'sobrannyepk': frozenset({'ram_gb', 'storage_gb'}),
    'monobloki': frozenset({'ram_gb', 'storage_gb'}),
    'mikrokompyutery': frozenset({'ram_gb', 'storage_gb'}),
    # Оперативная память: одна линейка (Kingston FURY Beast DDR4 3200) —
    # разные объёмы и kit-комплекты (1x8, 2x8, 2x16).
    'operativnaya-pamyat': frozenset({'ram_gb', 'modules_count'}),
    'servernaya-pamyat': frozenset({'ram_gb', 'modules_count'}),

    # === Новые (с экстракторами model_code в family.py) ===
    # GPU: одна модель чипа — разные объёмы памяти (RTX 4060 8GB vs 12GB)
    'videokarty': frozenset({'memory_gb'}),
    # Мониторы: одна линейка — разные размеры/разрешения (LG 27UP650 vs 32UP650)
    'monitory': frozenset({'screen_in', 'resolution'}),
    # CPU/MB/PSU обычно без вариантов (каждая модель = свой Product),
    # но включаем в систему для дедупликации между источниками.
    'processory': frozenset(),
    'servernye-processory': frozenset(),
    'materinskie-platy': frozenset(),
    'servernye-materinskie-platy': frozenset(),
    'bloki-pitaniya': frozenset(),
    'servernye-bloki-pitaniya': frozenset(),

    # === Этап A: simple категории ===
    # Карты памяти: одна модель — разные объёмы (Kingston Canvas Select Plus 64/128/512GB)
    'karty-pamyati': frozenset({'storage_gb'}),
    # Внешние HDD: одна модель — разные объёмы (WD My Passport 1/2/4TB)
    'vneshnie-zhestkie-diski': frozenset({'storage_gb'}),
    # Остальные обычно без вариантов
    'mikrofony': frozenset(),
    'zvukovye-karty': frozenset(),
    'setevye-hranilisha': frozenset(),
    'ohlazhdenie-dlya-servernyh-processorov': frozenset(),
    'servernye-korpusa': frozenset(),
    'naushniki': frozenset(),

    # === Этап B: периферия (brand dictionary) ===
    'myshi': frozenset(),
    'klaviatury': frozenset(),
    'korpusa': frozenset(),
}


# Дефолт для категорий без специфичных правил — вариантов нет, каждый Product
# уникален (процессоры, БП, корпуса, материнки и т. п.).
VARIANT_SPEC_KEYS_DEFAULT: frozenset[str] = frozenset()


def get_variant_keys(category_slug: str) -> frozenset[str]:
    return VARIANT_SPEC_KEYS_BY_CATEGORY.get(
        (category_slug or '').strip().lower(),
        VARIANT_SPEC_KEYS_DEFAULT,
    )


__all__ = (
    'AUTO_MERGE_THRESHOLD',
    'REVIEW_THRESHOLD',
    'WEIGHTS',
    'NAME_DICE_WEIGHT',
    'SOFT_CONFLICT_PENALTY',
    'HARD_REJECT_KEYS',
    'TRUSTED_MPN_SOURCES',
    'WEAK_SOURCES',
    'BRAND_ALIASES',
    'CPU_FAMILIES',
    'GPU_FAMILIES',
    'COLORS',
    'RE_BRACKET_MPN',
    'RE_FREE_MPN',
    'VARIANT_SPEC_KEYS_BY_CATEGORY',
    'VARIANT_SPEC_KEYS_DEFAULT',
    'get_variant_keys',
)
