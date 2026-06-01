from django.db import migrations


def backfill_offer_prices(apps, schema_editor):
    """Заполняет денормализованные Offer.current_price из последней is_actual PriceHistory.

    Источник истины остаётся PriceHistory; копируем актуальную цену в оффер, чтобы
    листинг/дашборд читали её без N+1. Дальше поля обновляет task_save_price.
    """
    Offer = apps.get_model('products', 'Offer')
    PriceHistory = apps.get_model('prices', 'PriceHistory')

    for offer in Offer.objects.all().iterator():
        last = (
            PriceHistory.objects
            .filter(offer_id=offer.pk, is_actual=True)
            .order_by('-timestamp')
            .first()
        )
        if last is None:
            continue
        offer.current_price = last.price
        offer.current_old_price = last.old_price
        offer.price_updated_at = last.timestamp
        offer.save(update_fields=['current_price', 'current_old_price', 'price_updated_at'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0023_offer_current_old_price_offer_current_price_and_more'),
        ('prices', '0011_alter_parserun_source_alter_pricehistory_source'),
    ]

    operations = [
        migrations.RunPython(backfill_offer_prices, noop_reverse),
    ]
