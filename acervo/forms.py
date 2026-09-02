from django import forms

from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'tipo',
            'codigo_barras',
            'titulo',
            'artista_diretor',
            'ano',
            'categoria',
            'gravadora_distribuidora',
            'descricao',
            'estado_conservacao',
            'preco',
            'localizacao',
            'status',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'preco': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'ano': forms.NumberInput(attrs={'min': '0'}),
        }
        labels = {
            'codigo_barras': 'Código de barras',
            'artista_diretor': 'Artista ou Diretor',
            'gravadora_distribuidora': 'Gravadora ou Distribuidora',
            'descricao': 'Descrição',
            'estado_conservacao': 'Estado de conservação',
            'preco': 'Preço',
            'localizacao': 'Localização',
        }
