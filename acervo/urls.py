from django.urls import path

from . import views
from . import import_views
from integracoes.views import metadados

app_name = 'acervo'

urlpatterns = [
    path('metadados/', metadados, name='metadados'),
    path('importar/', import_views.importar, name='importar_csv'),
    path('importar/<uuid:pk>/', import_views.previa, name='previa_csv'),
    path('', views.lista, name='lista'),
    path('cadastrar/', views.cadastrar, name='cadastrar'),
    path('item/<int:pk>/', views.detalhe, name='detalhe'),
    path('item/<int:pk>/editar/', views.editar, name='editar'),
    path('item/<int:pk>/excluir/', views.excluir, name='excluir'),
]
