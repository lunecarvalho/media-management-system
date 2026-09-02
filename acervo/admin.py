from django.contrib import admin
from .models import Item, Categoria


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'codigo_barras', 'categoria', 'status', 'data_cadastro']
    list_filter = ['tipo', 'status', 'categoria', 'estado_conservacao']
    search_fields = ['titulo', 'artista_diretor', 'codigo_barras']
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('tipo', 'titulo', 'artista_diretor', 'codigo_barras')
        }),
        ('Detalhes', {
            'fields': ('categoria', 'ano', 'gravadora_distribuidora', 'descricao')
        }),
        ('Física', {
            'fields': ('estado_conservacao', 'localizacao')
        }),
        ('Comercial', {
            'fields': ('preco', 'status')
        }),
        ('Sistema', {
            'fields': ('usuario_responsavel', 'data_cadastro', 'data_atualizacao'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['data_cadastro', 'data_atualizacao']
