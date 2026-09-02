from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'itens', views.ItemViewSet, basename='item')
router.register(r'categorias', views.CategoriaViewSet, basename='categoria')
router.register(r'movimentacoes', views.MovimentacaoViewSet, basename='movimentacao')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
]
