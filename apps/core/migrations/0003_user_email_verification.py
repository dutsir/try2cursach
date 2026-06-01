from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_user_accepted_terms_user_accepted_terms_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='notify_email',
            field=models.BooleanField(default=True, verbose_name='Дублировать уведомления на email'),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Email подтверждён'),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verify_token',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='Токен верификации'),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verify_sent_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Письмо отправлено'),
        ),
    ]
