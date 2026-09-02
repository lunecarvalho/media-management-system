from django.contrib.auth.models import User
from django.shortcuts import render


def lista(request):
    usuarios = User.objects.select_related('perfil').order_by('username')
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios})
