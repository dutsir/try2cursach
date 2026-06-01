from django.conf import settings
from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth с CSRF, отключённым только в режиме разработки.

    В DEBUG Vite-прокси шлёт Origin: localhost:5173 на Django :8000 — это
    триггерит cross-origin CSRF-проверку Django и даёт 403 даже при валидном
    токене. Поэтому в dev CSRF не форсим.

    В production (DEBUG=0) включаем штатную CSRF-проверку: фронт читает cookie
    `csrftoken` и шлёт его в заголовке X-CSRFToken (см. frontend/src/api/client.ts),
    cookie проставляется на GET /api/auth/me|login (декоратор ensure_csrf_cookie).
    Анонимные запросы (login/register) CSRF не проверяются — у них нет сессии.
    """

    def enforce_csrf(self, request):
        if settings.DEBUG:
            return
        return super().enforce_csrf(request)
