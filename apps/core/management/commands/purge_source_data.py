"""Удаление спарсенных данных одного магазина (офферы, цены, сироты Product)."""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Count, F, Q

from apps.prices.models import ParseRun, PriceHistory
from apps.products.models import CategoryListing, MatchReview, Offer, Product


class Command(BaseCommand):
    help = (
        'Удалить офферы и историю цен магазина (ozon/citilink/dns). '
        'Product без оставшихся офферов удаляются. По умолчанию dry-run.'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--source',
            required=True,
            choices=[c[0] for c in Offer.Source.choices],
            help='Магазин: ozon, citilink, dns',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Реально удалить (без флага — только подсчёт).',
        )
        parser.add_argument(
            '--deactivate-listings',
            action='store_true',
            help='Отключить CategoryListing этого магазина (is_active=False).',
        )

    def handle(self, *args: Any, **options: Any) -> None:
        source = options['source']
        apply = bool(options['apply'])
        deactivate_listings = bool(options['deactivate_listings'])

        offer_ids = list(
            Offer.objects.filter(source=source).values_list('pk', flat=True)
        )
        product_ids = set(
            Offer.objects.filter(source=source).values_list('product_id', flat=True)
        )

        ph_by_offer = (
            PriceHistory.objects.filter(offer_id__in=offer_ids).count()
            if offer_ids else 0
        )
        ph_by_source = PriceHistory.objects.filter(source=source).count()

        orphan_after = list(
            Product.objects.filter(pk__in=product_ids)
            .annotate(
                src_n=Count('offers', filter=Q(offers__source=source)),
                total_n=Count('offers'),
            )
            .filter(src_n=F('total_n'))
            .values_list('pk', flat=True)
        )

        reviews = (
            MatchReview.objects.filter(offer_id__in=offer_ids).count()
            if offer_ids else 0
        )
        parse_runs = ParseRun.objects.filter(source=source).count()
        listings = CategoryListing.objects.filter(source=source, is_active=True).count()

        mode = 'APPLY' if apply else 'DRY-RUN'
        self.stdout.write(self.style.NOTICE(f'Источник: {source}, режим: {mode}'))
        self.stdout.write(f'  Offer: {len(offer_ids)}')
        self.stdout.write(f'  PriceHistory (по offer): {ph_by_offer}')
        self.stdout.write(f'  PriceHistory (source={source}, всего): {ph_by_source}')
        self.stdout.write(f'  MatchReview: {reviews}')
        self.stdout.write(
            f'  Product удалятся (только {source}): {len(orphan_after)}'
        )
        self.stdout.write(
            f'  Product останутся (есть dns/citilink): '
            f'{len(product_ids) - len(orphan_after)}'
        )
        self.stdout.write(f'  ParseRun: {parse_runs}')
        if deactivate_listings:
            self.stdout.write(f'  CategoryListing отключить: {listings}')

        if not apply:
            self.stdout.write(self.style.WARNING(
                '\nНичего не удалено. Добавьте --apply для выполнения.'
            ))
            return

        if not offer_ids and ph_by_source == 0:
            self.stdout.write(self.style.WARNING('Нечего удалять.'))
            return

        with transaction.atomic():
            deleted_reviews, _ = MatchReview.objects.filter(
                offer_id__in=offer_ids,
            ).delete()
            deleted_ph, _ = PriceHistory.objects.filter(
                Q(offer_id__in=offer_ids) | Q(source=source),
            ).delete()
            deleted_offers, _ = Offer.objects.filter(source=source).delete()

            deleted_products, _ = (
                Product.objects.filter(pk__in=orphan_after)
                .annotate(n=Count('offers'))
                .filter(n=0)
                .delete()
            )

            deleted_runs, _ = ParseRun.objects.filter(source=source).delete()

            listings_updated = 0
            if deactivate_listings:
                listings_updated = CategoryListing.objects.filter(
                    source=source, is_active=True,
                ).update(is_active=False)

        self.stdout.write(self.style.SUCCESS('\nУдалено:'))
        self.stdout.write(f'  MatchReview: {deleted_reviews}')
        self.stdout.write(f'  PriceHistory: {deleted_ph}')
        self.stdout.write(f'  Offer: {deleted_offers}')
        self.stdout.write(f'  Product: {deleted_products}')
        self.stdout.write(f'  ParseRun: {deleted_runs}')
        if deactivate_listings:
            self.stdout.write(
                f'  CategoryListing is_active=False: {listings_updated}'
            )
