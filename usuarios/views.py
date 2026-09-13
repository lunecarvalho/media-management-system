from config.pagination import paginar
from django.contrib.auth.models import User
from django.shortcuts import render


def lista(request):
    usuarios = User.objects.select_related('perfil').order_by('username')
    usuarios = paginar(request, usuarios)
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios, 'page_obj': usuarios})
