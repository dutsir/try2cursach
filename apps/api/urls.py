from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('wishlist', views.WishlistViewSet, basename='wishlist')
router.register('build', views.BuildViewSet, basename='build')

urlpatterns = [
    path('', include(router.urls)),
    path('categories/<slug:slug>/facets/', views.CategoryFacetsView.as_view(), name='category-facets'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('compare/', views.CompareView.as_view(), name='compare'),
    path('compare/ai-summary/', views.AICompareSummaryView.as_view(), name='compare-ai-summary'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),
    path('auth/verify-email/', views.verify_email, name='verify-email'),
    path('auth/resend-verification/', views.resend_verification, name='resend-verification'),
    path('auth/password-reset/', views.password_reset_request, name='password-reset'),
    path('auth/password-reset-confirm/', views.password_reset_confirm, name='password-reset-confirm'),
    path('auth/change-password/', views.change_password, name='change-password'),
    path('auth/change-email/', views.change_email, name='change-email'),
    path('telegram/link/', views.telegram_link, name='telegram-link'),
    path('telegram/status/', views.telegram_status, name='telegram-status'),
    path('telegram/unlink/', views.telegram_unlink, name='telegram-unlink'),
]
