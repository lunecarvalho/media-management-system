from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from . import views

urlpatterns = [
    path('health/', views.health, name='health'),
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', views.dashboard, name='dashboard'),
    path('codigo-barras/', views.codigo_barras, name='codigo_barras'),
    path('configuracoes/', views.configuracoes, name='configuracoes'),
    path('acervo/', include('acervo.urls')),
    path('movimentacoes/', include('movimentacoes.urls')),
    path('categorias/', include('categorias.urls')),
    path('usuarios/', include('usuarios.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
