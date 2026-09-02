from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Perfil


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = 'Perfil'


class UsuarioAdmin(BaseUserAdmin):
    inlines = [PerfilInline]


# Desregistrar User padrão e registrar com Perfil
admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'tipo', 'ativo']
    list_filter = ['tipo', 'ativo']
