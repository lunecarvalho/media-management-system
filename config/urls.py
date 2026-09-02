from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', TemplateView.as_view(template_name='dashboard-fixed.html'), name='dashboard'),
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
