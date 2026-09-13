from django.contrib import admin
from django import forms
from .models import Categoria, Produto, Exemplar
from .services import salvar_exemplar, salvar_produto, COPY_FIELDS, validate_transition

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'descricao']
    search_fields = ['nome']

@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'tipo', 'ean', 'categoria']
    search_fields = ['titulo', 'ean', 'artista_diretor']
    readonly_fields = ['identificadores', 'metadados', 'origem']
    def save_model(self, request, obj, form, change):
        salvar_produto(obj, request.user)

class ExemplarAdminForm(forms.ModelForm):
    class Meta:
        model = Exemplar
        fields = '__all__'
    def clean(self):
        data = super().clean()
        if self.instance.pk and data.get('status'):
            old = Exemplar.objects.get(pk=self.instance.pk)
            validate_transition(old.status, data['status'])
        elif data.get('status') != 'disponivel':
            self.add_error('status', 'Novos exemplares entram como disponíveis.')
        return data

@admin.register(Exemplar)
class ExemplarAdmin(admin.ModelAdmin):
    form = ExemplarAdminForm
    list_display = ['codigo_interno', 'produto', 'status', 'preco']
    list_filter = ['status', 'estado_conservacao', 'produto__tipo']
    search_fields = ['codigo_interno', 'produto__titulo', 'produto__ean']
    readonly_fields = ['data_cadastro', 'data_atualizacao', 'usuario_responsavel']
    def save_model(self, request, obj, form, change):
        saved = salvar_exemplar(usuario=request.user, dados={f: getattr(obj, f) for f in COPY_FIELDS},
                                exemplar=obj if change else None)
        obj.pk = saved.pk
        obj.usuario_responsavel = saved.usuario_responsavel
    def has_delete_permission(self, request, obj=None):
        return False  # Retirar via status cancelado; não apagar trilha de auditoria.
