from django.urls import path

from . import views

app_name = 'acervo'

urlpatterns = [
    path('', views.lista, name='lista'),
    path('cadastrar/', views.cadastrar, name='cadastrar'),
    path('item/<int:pk>/', views.detalhe, name='detalhe'),
    path('item/<int:pk>/editar/', views.editar, name='editar'),
    path('item/<int:pk>/excluir/', views.excluir, name='excluir'),
]
