from django import forms
from django.db import transaction
from .models import Exemplar, Produto
from .services import salvar_exemplar, salvar_produto, validate_transition


class CSVUploadForm(forms.Form):
    arquivo = forms.FileField(label='Arquivo CSV UTF-8')

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['tipo', 'titulo', 'artista_diretor', 'ean', 'categoria', 'ano', 'gravadora_distribuidora', 'descricao']

class ItemForm(forms.ModelForm):
    class Meta:
        model = Exemplar
        fields = ['produto', 'codigo_interno', 'estado_conservacao', 'preco', 'localizacao', 'status']
        widgets = {'preco': forms.NumberInput(attrs={'step': '0.01', 'min': '0'})}

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        self.original_status = self.instance.status if self.instance.pk else None
        self.fields['produto'].required = False
        self.fields['produto'].help_text = 'Selecione um produto existente ou preencha os dados abaixo.'
        self.product_form = ProdutoForm(self.data if self.is_bound else None, prefix='produto')
        self.product_form.use_required_attribute = False
        if self.instance.pk:
            self.fields['produto'].required = True

    def clean(self):
        data = super().clean()
        if self.original_status and data.get('status'):
            validate_transition(self.original_status, data['status'], self.usuario)
        elif data.get('status') and data['status'] != 'disponivel':
            self.add_error('status', 'Novos exemplares entram como disponíveis.')
        return data

    def is_valid(self):
        valid = super().is_valid()
        if self.cleaned_data.get('produto'):
            return valid
        return self.product_form.is_valid() and valid

    @transaction.atomic
    def save(self, commit=True):
        if not commit or self.usuario is None:
            raise ValueError('Informe usuario e utilize commit=True.')
        product = self.cleaned_data.get('produto')
        if not product:
            product = salvar_produto(self.product_form.save(commit=False), self.usuario)
        data = {f: self.cleaned_data[f] for f in self.Meta.fields}
        data['produto'] = product
        self.instance = salvar_exemplar(usuario=self.usuario, dados=data,
                                       exemplar=self.instance if self.instance.pk else None)
        return self.instance
