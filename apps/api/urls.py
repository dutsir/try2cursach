from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('offers', views.OfferViewSet, basename='offer')
router.register('subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('anomalies', views.AnomalyViewSet, basename='anomaly')
router.register('wishlist', views.WishlistViewSet, basename='wishlist')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),
]
