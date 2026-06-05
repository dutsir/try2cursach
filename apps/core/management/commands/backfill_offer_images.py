from __future__ import annotations

import html
import json
import logging
import random
import re
import time
from urllib.parse import urljoin

import requests
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q
from django.utils import timezone

from apps.products.models import Offer
from apps.prices.wildberries_parser import get_image_url as wb_get_image_url

logger = logging.getLogger(__name__)

_META_RE = re.compile(
    r"""<meta\s+[^>]*(?:property|name)\s*=\s*["'](?P<key>[^"']+)["'][^>]*>""",
    flags=re.IGNORECASE,
)
_CONTENT_RE = re.compile(r"""content\s*=\s*["'](?P<content>[^"']+)["']""", flags=re.IGNORECASE)
_LDJSON_RE = re.compile(
    r"""<script[^>]*type=["']application/ld\+json["'][^>]*>(?P<json>.*?)</script>""",
    flags=re.IGNORECASE | re.DOTALL,
)
_WB_NM_FROM_URL_RE = re.compile(r"""/catalog/(?P<nm>\d+)/""", flags=re.IGNORECASE)
_PLACEHOLDER_IMG_RE = re.compile(r"""placeholder|no-?image|stub|spacer|loader""", flags=re.IGNORECASE)


def _extract_meta_image(html_text: str) -> str:
    if not html_text:
        return ""

    for m in _META_RE.finditer(html_text):
        key = (m.group("key") or "").strip().lower()
        if key not in {"og:image", "twitter:image"}:
            continue
        tag = m.group(0)
        cm = _CONTENT_RE.search(tag)
        if not cm:
            continue
        value = html.unescape((cm.group("content") or "").strip())
        if value and not value.startswith("data:") and not value.startswith("blob:"):
            return value
    return ""


def _iter_ldjson_images(node: object) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        image = node.get("image")
        if isinstance(image, str):
            out.append(image)
        elif isinstance(image, list):
            out.extend(str(x) for x in image if isinstance(x, str))
        elif isinstance(image, dict):
            url = image.get("url")
            if isinstance(url, str):
                out.append(url)
        for val in node.values():
            out.extend(_iter_ldjson_images(val))
    elif isinstance(node, list):
        for item in node:
            out.extend(_iter_ldjson_images(item))
    return out


def _extract_ldjson_image(html_text: str) -> str:
    if not html_text:
        return ""
    for match in _LDJSON_RE.finditer(html_text):
        raw = (match.group("json") or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        for candidate in _iter_ldjson_images(payload):
            clean = html.unescape(candidate.strip())
            if clean and not clean.startswith("data:") and not clean.startswith("blob:"):
                return clean
    return ""


def _extract_best_image(html_text: str) -> str:
    return _extract_meta_image(html_text) or _extract_ldjson_image(html_text)


def _normalize_image_url(page_url: str, raw_image_url: str) -> str:
    if not raw_image_url:
        return ""
    u = raw_image_url.strip()
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return urljoin(page_url, u)
    return u


def _is_placeholder_image(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return True
    return bool(_PLACEHOLDER_IMG_RE.search(u))


def _extract_wb_nm_id(offer: Offer) -> int | None:
    candidates = [
        (offer.source_sku or "").strip(),
        (offer.vendor_code or "").strip(),
        (getattr(offer.product, "vendor_code", "") or "").strip(),
    ]
    for raw in candidates:
        if raw.isdigit():
            try:
                return int(raw)
            except Exception:
                continue

    url = (offer.url or "").strip()
    if not url:
        return None
    m = _WB_NM_FROM_URL_RE.search(url)
    if m:
        try:
            return int(m.group("nm"))
        except Exception:
            return None
    return None


def _build_wb_image_url(offer: Offer) -> str:
    nm_id = _extract_wb_nm_id(offer)
    if not nm_id:
        return ""
    # c516x688 = основной размер, fallback на big для части старых карточек.
    return wb_get_image_url(nm_id, size="c516x688") or wb_get_image_url(nm_id, size="big")


class Command(BaseCommand):
    help = "Дозаполняет Offer.image_url из og:image/twitter:image карточки товара."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source",
            type=str,
            default="citilink",
            help="Источник офферов (по умолчанию: citilink).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=300,
            help="Максимум офферов за прогон (по умолчанию: 300).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=12.0,
            help="HTTP timeout в секундах (по умолчанию: 12).",
        )
        parser.add_argument(
            "--sleep-min",
            type=float,
            default=0.3,
            help="Минимальная пауза между запросами (по умолчанию: 0.3).",
        )
        parser.add_argument(
            "--sleep-max",
            type=float,
            default=0.9,
            help="Максимальная пауза между запросами (по умолчанию: 0.9).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Применить изменения в БД. Без флага — только dry-run.",
        )
        parser.add_argument(
            "--fill-product-image",
            action="store_true",
            help="Если у Product.image_url пусто, копировать туда найденную картинку Offer.",
        )
        parser.add_argument(
            "--rebuild-existing",
            action="store_true",
            help="Перестроить image_url даже у уже заполненных Offer (особенно полезно для wb).",
        )
        parser.add_argument(
            "--upgrade-product-image",
            action="store_true",
            help="Обновлять Product.image_url даже если не пусто (когда там placeholder/битый URL).",
        )

    def handle(self, *args, **options) -> None:
        source = (options["source"] or "").strip().lower()
        limit = max(1, int(options["limit"]))
        timeout = max(1.0, float(options["timeout"]))
        sleep_min = max(0.0, float(options["sleep_min"]))
        sleep_max = max(sleep_min, float(options["sleep_max"]))
        apply = bool(options["apply"])
        fill_product_image = bool(options["fill_product_image"])
        rebuild_existing = bool(options["rebuild_existing"])
        upgrade_product_image = bool(options["upgrade_product_image"])

        self.stdout.write(
            self.style.NOTICE(
                f"backfill_offer_images: source={source}, limit={limit}, "
                f"mode={'APPLY' if apply else 'DRY-RUN'}"
            )
        )

        qs = (
            Offer.objects
            .filter(source=source)
            .exclude(url="")
            .select_related("product")
            .order_by("-updated_at", "id")
        )
        if not rebuild_existing:
            qs = qs.filter(Q(image_url="") | Q(image_url__isnull=True))
        offers = list(qs[:limit])
        if not offers:
            self.stdout.write(self.style.WARNING("Офферов с пустой картинкой не найдено."))
            return

        self.stdout.write(f"К обработке: {len(offers)}")
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )

        ok = 0
        failed = 0
        updated_product = 0

        for i, offer in enumerate(offers, start=1):
            try:
                if source == "wb":
                    image_url = _build_wb_image_url(offer)
                else:
                    resp = session.get(offer.url, timeout=timeout, allow_redirects=True)
                    if resp.status_code >= 400:
                        failed += 1
                        logger.info(
                            "backfill_offer_images: offer=%s status=%s url=%s",
                            offer.pk, resp.status_code, offer.url,
                        )
                        continue
                    raw_image = _extract_best_image(resp.text or "")
                    image_url = _normalize_image_url(resp.url or offer.url, raw_image)
                if not image_url:
                    failed += 1
                    continue

                ok += 1
                if apply:
                    offer_image_before = (offer.image_url or "").strip()
                    should_write_offer = (
                        rebuild_existing
                        or not offer_image_before
                        or _is_placeholder_image(offer_image_before)
                    )
                    if should_write_offer and offer_image_before != image_url:
                        offer.image_url = image_url[:1024]
                        offer.last_seen_at = timezone.now()
                        offer.save(update_fields=["image_url", "last_seen_at", "updated_at"])

                    if fill_product_image and offer.product:
                        product_image_before = (offer.product.image_url or "").strip()
                        can_update_product = (
                            (not product_image_before)
                            or (upgrade_product_image and _is_placeholder_image(product_image_before))
                        )
                        if can_update_product and product_image_before != image_url:
                            offer.product.image_url = image_url[:1024]
                            offer.product.save(update_fields=["image_url", "updated_at"])
                            updated_product += 1

                if i <= 10:
                    self.stdout.write(
                        f"  [{i}/{len(offers)}] offer_id={offer.pk} -> {image_url}"
                    )
            except Exception as exc:
                failed += 1
                logger.debug(
                    "backfill_offer_images: offer=%s url=%s error=%s",
                    offer.pk, offer.url, exc, exc_info=True,
                )
            finally:
                if i < len(offers):
                    time.sleep(random.uniform(sleep_min, sleep_max))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: найдено картинок={ok}, без результата/ошибок={failed}, "
                f"изменения={'применены' if apply else 'не применялись'}."
            )
        )
        if apply and fill_product_image:
            self.stdout.write(f"Product.image_url обновлено: {updated_product}")
