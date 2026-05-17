from __future__ import annotations

import html
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

logger = logging.getLogger(__name__)

_META_RE = re.compile(
    r"""<meta\s+[^>]*(?:property|name)\s*=\s*["'](?P<key>[^"']+)["'][^>]*>""",
    flags=re.IGNORECASE,
)
_CONTENT_RE = re.compile(r"""content\s*=\s*["'](?P<content>[^"']+)["']""", flags=re.IGNORECASE)


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

    def handle(self, *args, **options) -> None:
        source = (options["source"] or "").strip().lower()
        limit = max(1, int(options["limit"]))
        timeout = max(1.0, float(options["timeout"]))
        sleep_min = max(0.0, float(options["sleep_min"]))
        sleep_max = max(sleep_min, float(options["sleep_max"]))
        apply = bool(options["apply"])
        fill_product_image = bool(options["fill_product_image"])

        self.stdout.write(
            self.style.NOTICE(
                f"backfill_offer_images: source={source}, limit={limit}, "
                f"mode={'APPLY' if apply else 'DRY-RUN'}"
            )
        )

        qs = (
            Offer.objects
            .filter(source=source)
            .filter(Q(image_url="") | Q(image_url__isnull=True))
            .exclude(url="")
            .select_related("product")
            .order_by("-updated_at", "id")
        )
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
                resp = session.get(offer.url, timeout=timeout, allow_redirects=True)
                if resp.status_code >= 400:
                    failed += 1
                    logger.info(
                        "backfill_offer_images: offer=%s status=%s url=%s",
                        offer.pk, resp.status_code, offer.url,
                    )
                    continue
                raw_image = _extract_meta_image(resp.text or "")
                image_url = _normalize_image_url(resp.url or offer.url, raw_image)
                if not image_url:
                    failed += 1
                    continue

                ok += 1
                if apply:
                    offer.image_url = image_url[:1024]
                    offer.last_seen_at = timezone.now()
                    offer.save(update_fields=["image_url", "last_seen_at", "updated_at"])
                    if fill_product_image and offer.product and not (offer.product.image_url or "").strip():
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
