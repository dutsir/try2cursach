from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('products', views.ProductViewSet, basename='product')
router.register('families', views.ProductFamilyViewSet, basename='family')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('offers', views.OfferViewSet, basename='offer')
router.register('subscriptions', views.SubscriptionViewSet, basename='subscription')
router.register('notifications', views.NotificationViewSet, basename='notification')
router.register('wishlist', views.WishlistViewSet, basename='wishlist')

urlpatterns = [
    path('', include(router.urls)),
    path('categories/<slug:slug>/facets/', views.CategoryFacetsView.as_view(), name='category-facets'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('compare/', views.CompareView.as_view(), name='compare'),
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.me_view, name='me'),
]
