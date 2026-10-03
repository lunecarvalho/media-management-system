from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Perfil


class UsuarioCriacaoForm(UserCreationForm):
    tipo = forms.ChoiceField(label='Perfil', choices=Perfil.TIPO_CHOICES)
    ativo = forms.BooleanField(label='Usuário ativo', required=False, initial=True)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')
        labels = {
            'username': 'Nome de usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
        }


class UsuarioEdicaoForm(forms.ModelForm):
    tipo = forms.ChoiceField(label='Perfil', choices=Perfil.TIPO_CHOICES)
    ativo = forms.BooleanField(label='Usuário ativo', required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')
        labels = {
            'username': 'Nome de usuário',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'email': 'E-mail',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        perfil = Perfil.objects.filter(usuario=self.instance).first()
        self.fields['tipo'].initial = perfil.tipo if perfil else 'funcionario'
        self.fields['ativo'].initial = self.instance.is_active and (perfil.ativo if perfil else False)