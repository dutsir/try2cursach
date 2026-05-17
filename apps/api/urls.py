from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('offers', views.OfferViewSet, basename='offer')
router.register('subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('anomalies', views.AnomalyViewSet, basename='anomaly')

urlpatterns = [
    path('', include(router.urls)),
]
