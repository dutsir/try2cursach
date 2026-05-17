from django.urls import path, re_path

from . import views

app_name = 'catalog'


urlpatterns = [
    path('', views.catalog_index, name='index'),
    re_path(r'^category/(?P<slug>[^/]+)/$', views.category_detail, name='category'),
    re_path(r'^product/(?P<slug>[^/]+)/$', views.product_detail, name='product'),
]
