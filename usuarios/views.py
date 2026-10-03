from config.pagination import paginar
from django.contrib import messages
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import UsuarioCriacaoForm, UsuarioEdicaoForm
from .models import Perfil


def lista(request):
    usuarios = User.objects.select_related('perfil').order_by('username')
    usuarios = paginar(request, usuarios)
    return render(request, 'usuarios/lista.html', {'usuarios': usuarios, 'page_obj': usuarios})


def criar(request):
    form = UsuarioCriacaoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            usuario = form.save()
            Perfil.objects.create(usuario=usuario, tipo=form.cleaned_data['tipo'], ativo=form.cleaned_data['ativo'])
            usuario.is_active = form.cleaned_data['ativo']
            usuario.save(update_fields=['is_active'])
        messages.success(request, 'Usuário criado.')
        return redirect('usuarios:lista')
    return render(request, 'usuarios/form.html', {'form': form})


def editar(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    form = UsuarioEdicaoForm(request.POST or None, instance=usuario)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            usuario = form.save(commit=False)
            usuario.is_active = form.cleaned_data['ativo']
            usuario.save()
            Perfil.objects.update_or_create(
                usuario=usuario,
                defaults={'tipo': form.cleaned_data['tipo'], 'ativo': form.cleaned_data['ativo']},
            )
        messages.success(request, 'Usuário atualizado.')
        return redirect('usuarios:lista')
    return render(request, 'usuarios/form.html', {'form': form, 'usuario': usuario})


def _erro_exclusao(request, usuario):
    if usuario.pk == request.user.pk:
        return 'Você não pode remover a própria conta.'
    if usuario.is_superuser and not request.user.is_superuser:
        return 'Somente um superuser pode remover outro superuser.'
    perfil = Perfil.objects.filter(usuario=usuario).first()
    if perfil and perfil.tipo == 'proprietario' and usuario.is_active and perfil.ativo:
        proprietarios_ativos = User.objects.filter(
            is_active=True, perfil__tipo='proprietario', perfil__ativo=True,
        ).count()
        if proprietarios_ativos <= 1:
            return 'O último proprietário ativo não pode ser removido.'
    return None


def excluir(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    erro = _erro_exclusao(request, usuario)
    if request.method == 'POST' and not erro:
        try:
            with transaction.atomic():
                usuario.delete()
        except ProtectedError:
            erro = 'Este usuário não pode ser removido porque possui registros vinculados.'
        else:
            messages.success(request, 'Usuário removido.')
            return redirect('usuarios:lista')
    return render(request, 'usuarios/excluir.html', {'usuario': usuario, 'erro': erro})
