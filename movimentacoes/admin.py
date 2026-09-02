from django.contrib import admin
from .models import Movimentacao


@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ['item', 'tipo', 'usuario', 'data']
    list_filter = ['tipo', 'data', 'usuario']
    search_fields = ['item__titulo', 'usuario__username']
    readonly_fields = ['data']
