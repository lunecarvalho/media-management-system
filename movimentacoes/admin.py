from django.contrib import admin
from .models import Movimentacao

@admin.register(Movimentacao)
class MovimentacaoAdmin(admin.ModelAdmin):
    list_display = ['item', 'tipo', 'usuario', 'data']
    list_filter = ['tipo', 'data']
    search_fields = ['item__produto__titulo', 'usuario__username']
    readonly_fields = ['item', 'tipo', 'usuario', 'data', 'anterior', 'novo', 'detalhes']
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
