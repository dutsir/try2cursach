from django.contrib.auth.models import AbstractUser
from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField('Создано', auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Телефон', max_length=20, blank=True, default='')
    avatar = models.ImageField('Аватар', upload_to='avatars/', blank=True, null=True)

    # Согласие с условиями (фиксируем факт и момент принятия при регистрации).
    accepted_terms = models.BooleanField('Согласие с условиями', default=False)
    accepted_terms_at = models.DateTimeField('Согласие принято', null=True, blank=True)

    # Telegram-дублирование уведомлений. Бот не может писать по @username —
    # нужен chat_id, который ловим, когда пользователь сам пишет боту код привязки.
    telegram_chat_id = models.CharField(
        'Telegram chat_id', max_length=32, blank=True, default='', db_index=True,
    )
    telegram_username = models.CharField('Telegram username', max_length=64, blank=True, default='')
    telegram_link_code = models.CharField(
        'Код привязки Telegram', max_length=16, blank=True, default='', db_index=True,
    )
    telegram_link_expires_at = models.DateTimeField('Код привязки истекает', null=True, blank=True)
    telegram_linked_at = models.DateTimeField('Telegram привязан', null=True, blank=True)
    notify_telegram = models.BooleanField('Дублировать уведомления в Telegram', default=False)

    # Email-уведомления
    notify_email = models.BooleanField('Дублировать уведомления на email', default=True)

    # Верификация email
    email_verified = models.BooleanField('Email подтверждён', default=False, db_index=True)
    email_verify_token = models.CharField(
        'Токен верификации', max_length=64, blank=True, default='', db_index=True,
    )
    email_verify_sent_at = models.DateTimeField('Письмо отправлено', null=True, blank=True)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self) -> str:
        return self.username

    @property
    def telegram_linked(self) -> bool:
        return bool(self.telegram_chat_id)
