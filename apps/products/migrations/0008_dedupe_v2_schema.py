

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_category_groups_seed'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MatchReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('score', models.DecimalField(decimal_places=3, default=0, max_digits=4, verbose_name='Score')),
                ('signals', models.JSONField(blank=True, default=dict, verbose_name='Сигналы матчинга')),
                ('status', models.CharField(choices=[('pending', 'В ожидании'), ('approved', 'Одобрено'), ('rejected', 'Отклонено')], db_index=True, default='pending', max_length=16, verbose_name='Статус')),
                ('decided_at', models.DateTimeField(blank=True, null=True, verbose_name='Когда решено')),
                ('note', models.CharField(blank=True, default='', max_length=512, verbose_name='Комментарий')),
            ],
            options={
                'verbose_name': 'Заявка на ручной матчинг',
                'verbose_name_plural': 'Очередь ручного матчинга',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='MergeAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Создано')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Обновлено')),
                ('actor', models.CharField(choices=[('auto', 'Автоматический матчер'), ('manual', 'Ручная правка админа'), ('migration', 'Миграция/rebuild'), ('shadow', 'Shadow-прогон (без изменений в БД)')], max_length=16, verbose_name='Кто принял решение')),
                ('decision', models.CharField(choices=[('auto_merge', 'Автоматический merge'), ('review', 'Создан новый, кандидат в очередь review'), ('new', 'Создан новый Product'), ('update', 'Обновление существующего оффера')], max_length=16, verbose_name='Решение')),
                ('score', models.DecimalField(blank=True, decimal_places=3, default=0, max_digits=4, verbose_name='Score кандидата')),
                ('signals', models.JSONField(blank=True, default=dict, verbose_name='Сигналы матчинга')),
                ('run_id', models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='ID прогона')),
                ('reverted', models.BooleanField(default=False, verbose_name='Откачено')),
            ],
            options={
                'verbose_name': 'Запись аудита матчинга',
                'verbose_name_plural': 'Аудит матчинга',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='offer',
            name='confidence',
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=3, verbose_name='Уверенность матчинга'),
        ),
        migrations.AddField(
            model_name='offer',
            name='match_signals',
            field=models.JSONField(blank=True, default=dict, verbose_name='Сигналы матчинга'),
        ),
        migrations.AddField(
            model_name='offer',
            name='mpn_extracted',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='Извлечённый MPN'),
        ),
        migrations.AddField(
            model_name='offer',
            name='normalized_features',
            field=models.JSONField(blank=True, default=dict, verbose_name='Нормализованные фичи'),
        ),
        migrations.AddField(
            model_name='offer',
            name='raw_name',
            field=models.TextField(blank=True, default='', verbose_name='Исходное имя у магазина'),
        ),
        migrations.AddField(
            model_name='offer',
            name='source_sku',
            field=models.CharField(blank=True, db_index=True, default='', max_length=128, verbose_name='Артикул магазина (shop SKU)'),
        ),
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='Бренд'),
        ),
        migrations.AddField(
            model_name='product',
            name='key_hash',
            field=models.CharField(blank=True, db_index=True, default='', max_length=40, verbose_name='Хэш матчинг-ключа'),
        ),
        migrations.AddField(
            model_name='product',
            name='merge_locked',
            field=models.BooleanField(default=False, verbose_name='Запретить автоматический merge'),
        ),
        migrations.AddField(
            model_name='product',
            name='specs_fingerprint',
            field=models.JSONField(blank=True, default=dict, verbose_name='Структурированные характеристики'),
        ),
        migrations.AddIndex(
            model_name='offer',
            index=models.Index(fields=['source', 'mpn_extracted'], name='products_of_source_ba8ba5_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['brand', 'category'], name='products_pr_brand_c501a9_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['key_hash'], name='products_pr_key_has_fcaf7b_idx'),
        ),
        migrations.AddConstraint(
            model_name='offer',
            constraint=models.UniqueConstraint(condition=models.Q(('source_sku__gt', '')), fields=('source', 'source_sku'), name='offer_source_sku_unique'),
        ),
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(condition=models.Q(('vendor_code__gt', ''), ('brand__gt', '')), fields=('category', 'brand', 'vendor_code'), name='product_brand_mpn_in_category_unique'),
        ),
        migrations.AddField(
            model_name='matchreview',
            name='decided_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='match_decisions', to=settings.AUTH_USER_MODEL, verbose_name='Кто принял решение'),
        ),
        migrations.AddField(
            model_name='matchreview',
            name='offer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_reviews', to='products.offer', verbose_name='Оффер'),
        ),
        migrations.AddField(
            model_name='matchreview',
            name='suggested_product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='match_reviews', to='products.product', verbose_name='Предложенный мастер-товар'),
        ),
        migrations.AddField(
            model_name='mergeauditlog',
            name='from_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merge_audit_from', to='products.product', verbose_name='Старый мастер-товар'),
        ),
        migrations.AddField(
            model_name='mergeauditlog',
            name='offer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merge_audit', to='products.offer', verbose_name='Оффер'),
        ),
        migrations.AddField(
            model_name='mergeauditlog',
            name='to_product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='merge_audit_to', to='products.product', verbose_name='Новый мастер-товар'),
        ),
        migrations.AddIndex(
            model_name='matchreview',
            index=models.Index(fields=['status', '-created_at'], name='products_ma_status_1c770c_idx'),
        ),
        migrations.AddConstraint(
            model_name='matchreview',
            constraint=models.UniqueConstraint(fields=('offer', 'suggested_product'), name='match_review_offer_suggested_unique'),
        ),
        migrations.AddIndex(
            model_name='mergeauditlog',
            index=models.Index(fields=['actor', '-created_at'], name='products_me_actor_8f9588_idx'),
        ),
        migrations.AddIndex(
            model_name='mergeauditlog',
            index=models.Index(fields=['decision', '-created_at'], name='products_me_decisio_2ea620_idx'),
        ),
        migrations.AddIndex(
            model_name='mergeauditlog',
            index=models.Index(fields=['offer', '-created_at'], name='products_me_offer_i_e7bfd3_idx'),
        ),
    ]
