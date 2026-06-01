"""Межисточниковое сопоставление товаров (cross-source dedup).

Цель: один реальный товар, продающийся в DNS/Citilink/M.Video/WB, должен быть
ОДНИМ мастер-Product с офферами из разных источников — чтобы на фронте было видно
сравнение цен по 3-4 площадкам.

Подход — каноническая «сигнатура модели»: имя приводится к нормальному виду
(склейка номеров моделей «rtx 5060 ti» → «rtx5060ti», унификация объёмов памяти,
выкидывание шумовых/маркетинговых слов), после чего сравниваются значимые токены.

  - ТОЧНОЕ совпадение сигнатур (одинаковый brand) + непротиворечивые specs → уверенный
    матч (auto). EAGLE и AERO дают РАЗНЫЕ сигнатуры → НЕ сольются.
  - Высокая (но не точная) похожесть сигнатур (Dice ≥ порога) → пограничный матч (review).

Этот модуль НЕ трогает внутри-источниковую логику: cross-source матч допустим только
между офферами РАЗНЫХ источников (см. WITHIN_SOURCE_DEDUP_SOURCES в matcher.py).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Шумовые слова, не несущие смысла для идентификации модели.
# Бренд сравнивается отдельно, поэтому вендоров тоже можно убирать.
_NOISE_TOKENS: frozenset[str] = frozenset({
    # маркетинг / розница
    'новый', 'новая', 'новое', 'гарантия', 'оригинал', 'оригинальный', 'рф', 'ростест',
    'eac', 'ru', 'rus', 'retail', 'oem', 'ret', 'box', 'bulk', 'арт', 'art',
    # шина / разъёмы
    'pci', 'pcie', 'pci-e', 'express', 'hdmi', 'displayport', 'dp', 'dvi', 'vga',
    'usb', 'type', 'lan',
    # ВНИМАНИЕ: 'wifi' НЕ шум — наличие Wi-Fi различает SKU матплат
    # («Z790-P» vs «Z790-P WIFI»), пишется одинаково во всех источниках.
    # видеокарта-шум
    'видеокарта', 'видеокарты', 'geforce', 'nvidia', 'amd', 'radeon', 'intel',
    'graphics', 'gpu', 'бит', 'bit',
    # категориальные префиксы (DNS/Citilink/MVideo пишут их в начале имени,
    # WB — обычно нет; иначе сигнатуры одного товара расходятся между источниками)
    'материнская', 'плата', 'накопитель', 'накопители', 'блок', 'питания',
    'оперативная', 'память', 'модуль', 'процессор', 'монитор', 'корпус', 'кулер',
    'клавиатура', 'мышь', 'наушники', 'микрофон', 'диск', 'ssd', 'hdd', 'nvme',
    'твердотельный', 'внутренний', 'внешний', 'жесткий', 'жёсткий',
    # форм-фактор / сокет / частота — спецификация, не идентичность модели
    'socket', 'lga', 'atx', 'matx', 'mini', 'micro', 'itx', 'eatx', 'mhz', 'ghz',
    'мгц', 'ггц', 'вт', 'w', 'мм', 'mm',
    # generic
    'для', 'компьютера', 'пк', 'шт', 'игровой', 'игровая', 'с', 'и', 'в',
})

_WS_RE = re.compile(r'\s+')
_PUNCT_RE = re.compile(r'[^\w\s]', flags=re.UNICODE)

# Цвет — ПОЛНОЦЕННЫЙ дискриминатор SKU (белый ≠ чёрный = разные part-number, разные
# товары — владелец подтвердил, что цвета держим раздельно). НО цвет легко теряется:
# Citilink пишет его ПОСЛЕ запятой («…, без БП, белый [partno]»), а запятая-срез в
# _canonicalize его выкидывает → сигнатуры белого и чёрного Citilink схлопываются, и
# ни один не совпадает с DNS, где цвет до скобок сохраняется. Поэтому цвет извлекаем
# ОТДЕЛЬНО (из строки без скобок, ДО запятой-среза) и гарантированно дописываем в
# сигнатуру. Это лишь СУЖАЕТ сигнатуру (цвет добавляется) — ложных слияний не создаёт.
_COLOR_TOKENS: frozenset[str] = frozenset({
    'белый', 'белая', 'белое', 'white',
    'черный', 'черная', 'черное', 'black',  # ё→е делает _strip_accents
    'серый', 'серая', 'gray', 'grey',
    'серебристый', 'серебристая', 'silver',
    'красный', 'красная', 'red',
    'синий', 'синяя', 'blue',
    'зеленый', 'зеленая', 'green',
    'розовый', 'розовая', 'pink',
    'желтый', 'желтая', 'yellow',
    'золотистый', 'золотой', 'gold',
    'фиолетовый', 'purple',
    'оранжевый', 'orange',
    'бежевый', 'коричневый', 'голубой', 'бирюзовый',
})

# Спец-блоки в имени, которые есть у одних источников и нет у других:
# «[LGA 1700, Intel H610, 2xDDR4-3200 МГц, ...]», «(LGA1700, mATX)» — и хвост
# спецификаций после первой запятой. Удаляются ДО токенизации, иначе DNS/Citilink
# (спеки в имени) и WB (чистое короткое имя) дают разные сигнатуры одного товара.
_SPEC_BRACKET_RE = re.compile(r'\[[^\]]*\]|\([^)]*\)')

# Объём памяти в МБ → ГБ: «8192mb» / «8192 мб» → «8gb» (кратные 1024).
_MEM_MB_RE = re.compile(r'\b(\d{3,6})\s*(?:mb|мб)\b', flags=re.IGNORECASE)
# Объёмы памяти: «8 gb» / «8 гб» / «8g» → «8gb»; «1 tb» / «1 тб» → «1tb».
_MEM_GB_RE = re.compile(r'\b(\d+)\s*(?:gb|гб|g)\b', flags=re.IGNORECASE)
_MEM_TB_RE = re.compile(r'\b(\d+)\s*(?:tb|тб)\b', flags=re.IGNORECASE)

# Шум с цифрами, который НЕ идентифицирует конкретную модель (ширина шины, тип
# памяти, версия PCIe) — определяется чипом, одинаков у всех вариантов карты.
_NOISE_DIGIT_RE = (
    re.compile(r'^\d{2,4}bit$'),          # 128bit, 256bit
    re.compile(r'^gddr\d[a-z]?$'),        # gddr6, gddr6x, gddr7
    re.compile(r'^\d\.\d$'),              # 4.0 (версия PCIe)
)

# Склейка номеров моделей.
_LETTER_DIGIT_RE = re.compile(r'\b([a-zа-я]{1,5})\s+(\d{2,5})\b')        # rtx 5060 → rtx5060
_DIGIT_SUFFIX_RE = re.compile(r'\b([a-zа-я]*\d+)\s+(ti|xt|super|gre|x|s)\b')  # 5060 ti → 5060ti

# Буквенный суффикс модели после номера: «b760m k» → «b760mk», «z790 p» → «z790p»,
# «h610m h» → «h610mh». КРИТИЧНО для матплат/видеокарт: суффиксы -F/-K/-E/-A/-I — это
# РАЗНЫЕ модели. Одиночная буква иначе выбрасывается фильтром len<2, и разные платы
# (B760M-F vs B760M-K) сливаются в одну сигнатуру {b760m, prime}. Только латиница,
# чтобы не приклеить русские союзы «и»/«с» к номеру.
_MODEL_LETTER_SUFFIX_RE = re.compile(r'\b([a-z]*\d[a-z\d]*)\s+([a-z]{1,2})\b')


def _strip_accents(s: str) -> str:
    # ё→е: иначе «чёрный» (DNS) и «черный» (Citilink) — разные токены и цвет не матчится.
    return unicodedata.normalize('NFC', s or '').lower().replace('ё', 'е').strip()


def _canonicalize(name: str) -> str:
    s = _strip_accents(name)
    # Сначала срезаем спец-блоки «[...]»/«(...)» и хвост спецификаций после
    # первой запятой — они есть у DNS/Citilink/MVideo (спеки в имени) и нет у WB.
    # Без этого сигнатуры одного товара расходятся между источниками.
    s = _SPEC_BRACKET_RE.sub(' ', s)
    # Цвет извлекаем ДО запятой-среза (Citilink пишет его после запятой) и из строки
    # без скобок (чтобы не цеплять цвет из спец-блока). Дописываем в конец — переживёт срез.
    colors = {t for t in _WS_RE.sub(' ', _PUNCT_RE.sub(' ', s)).split() if t in _COLOR_TOKENS}
    s = s.split(',', 1)[0]
    s = _PUNCT_RE.sub(' ', s)
    s = _WS_RE.sub(' ', s).strip()
    # «8192mb» → «8gb» (до GB-регекса, чтобы объёмы в МБ и ГБ совпадали).
    s = _MEM_MB_RE.sub(lambda m: f'{int(m.group(1)) // 1024}gb', s)
    s = _MEM_GB_RE.sub(lambda m: f'{m.group(1)}gb', s)
    s = _MEM_TB_RE.sub(lambda m: f'{m.group(1)}tb', s)
    # Дважды прогоняем склейку: «rtx 5060 ti» → «rtx5060 ti» → «rtx5060ti».
    s = _LETTER_DIGIT_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}', s)
    s = _DIGIT_SUFFIX_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}', s)
    # Приклеиваем буквенный суффикс модели к номеру: «b760m f» → «b760mf».
    s = _MODEL_LETTER_SUFFIX_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}', s)
    # Гарантированно возвращаем цвет (мог быть срезан запятой у Citilink).
    if colors:
        s = f'{s} {" ".join(sorted(colors))}'
    return s


def _has_digit(tok: str) -> bool:
    return any(ch.isdigit() for ch in tok)


def model_signature(name: str, brand: str = '') -> frozenset[str]:
    """Возвращает множество значимых токенов модели для cross-source матчинга.

    Бренд НЕ включается в сигнатуру (сравнивается отдельно). Шумовые слова и
    короткие токены отбрасываются.
    """
    canon = _canonicalize(name)
    brand_tokens = {t for t in _canonicalize(brand).split() if t}
    tokens = set()
    for t in canon.split():
        if len(t) < 2:
            continue
        if t in _NOISE_TOKENS or t in brand_tokens:
            continue
        # Цифровой шум (ширина шины, тип/версия памяти) — общий для всех
        # вариантов чипа, не идентифицирует конкретную модель.
        if any(rx.match(t) for rx in _NOISE_DIGIT_RE):
            continue
        tokens.add(t)
    return frozenset(tokens)


def is_discriminating(sig: frozenset[str]) -> bool:
    """Сигнатура достаточно специфична (есть хотя бы один токен с цифрой)?

    Защищает от слияния по generic-названиям без модельного номера.
    """
    return any(_has_digit(t) for t in sig)


def model_tokens(sig: frozenset[str]) -> frozenset[str]:
    """Токены с цифрами — «идентичность» модели: чип, объём памяти и т.п.

    Если эти токены РАЗНЫЕ у двух товаров — это разные модели (другой чип/память),
    и совпадение прочих (маркетинговых) токенов не должно отправлять их в review.
    """
    return frozenset(t for t in sig if _has_digit(t))


def signature_dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return (2 * inter) / (len(a) + len(b))


def specs_conflict(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """Жёсткий конфликт по ключевым specs (память/диск/экран/чип)."""
    a = a or {}
    b = b or {}
    for key in ('ram_gb', 'storage_gb', 'screen_in', 'gpu_family', 'cpu_family'):
        av, bv = a.get(key), b.get(key)
        if av in (None, '') or bv in (None, ''):
            continue
        if str(av) != str(bv):
            return True
    return False
