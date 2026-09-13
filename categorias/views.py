from config.pagination import paginar
from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from acervo.models import Categoria
from .forms import CategoriaForm


def lista(request):
    form = CategoriaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Categoria criada.')
            return redirect('categorias:lista')
        except IntegrityError:
            form.add_error(None, 'Categoria já cadastrada por outra operação.')
    categorias = Categoria.objects.annotate(total_itens=Count('produto__exemplares')).order_by('nome')
    categorias = paginar(request, categorias)
    return render(request, 'categorias/lista.html', {'categorias': categorias, 'page_obj': categorias, 'form': form})


def editar(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    form = CategoriaForm(request.POST or None, instance=categoria)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            return redirect('categorias:lista')
        except IntegrityError:
            form.add_error(None, 'Nome de categoria já utilizado.')
    return render(request, 'categorias/form.html', {'form': form})


def excluir(request, pk):
    categoria = get_object_or_404(Categoria, pk=pk)
    erro = None
    if request.method == 'POST':
        try:
            categoria.delete()
            return redirect('categorias:lista')
        except ProtectedError:
            erro = 'A categoria possui produtos vinculados e não pode ser removida.'
    return render(request, 'categorias/excluir.html', {'categoria': categoria, 'erro': erro})
