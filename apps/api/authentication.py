from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication without CSRF enforcement.

    Vite's dev proxy sends Origin: localhost:5173 to Django on localhost:8000,
    which triggers Django's cross-origin CSRF check and causes 403s even when
    the CSRF token is present. Safe for same-host dev setups.
    """

    def enforce_csrf(self, request):
        pass
