from config.pagination import paginar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render

from django.core.exceptions import ValidationError
from .services import excluir_exemplar

from .forms import ItemForm
from .models import Categoria, Item


def lista(request):
    consulta = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    status = request.GET.get('status', '')

    itens = Item.objects.select_related('produto__categoria').all()
    if consulta:
        itens = itens.filter(
            Q(produto__titulo__icontains=consulta)
            | Q(produto__artista_diretor__icontains=consulta)
            | Q(codigo_interno__icontains=consulta)
        )
    if tipo in dict(Item.TIPO_CHOICES):
        itens = itens.filter(produto__tipo=tipo)
    if status in dict(Item.STATUS_CHOICES):
        itens = itens.filter(status=status)

    itens = paginar(request, itens)

    return render(
        request,
        'acervo/lista.html',
        {
            'itens': itens, 'page_obj': itens,
            'consulta': consulta,
            'tipo_atual': tipo,
            'status_atual': status,
        },
    )


@login_required
def cadastrar(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, usuario=request.user)
        if form.is_valid():
            try:
                item = form.save()
            except (ValidationError, IntegrityError) as exc:
                form.add_error(None, 'Dados invalidos ou conflito. Confira os campos e recarregue se necessario.')
                return render(request, 'acervo/cadastrar.html', {'form': form})
            messages.success(request, f'{item.titulo} foi adicionado ao acervo.')
            return redirect('acervo:lista')
    else:
        from .barcode_flow import dados_cadastro
        initial, product_initial, expired = dados_cadastro(request)
        form = ItemForm(initial=initial)
        form.product_form.initial.update(product_initial)
        if expired:
            messages.warning(request, 'Os metadados da leitura expiraram. Consulte novamente ou preencha os dados manualmente.')

    return render(
        request,
        'acervo/cadastrar.html',
        {'form': form, 'categorias': Categoria.objects.all()},
    )


def detalhe(request, pk):
    item = get_object_or_404(Item.objects.select_related('produto__categoria'), pk=pk)
    movimentacoes = item.movimentacoes.select_related('usuario').all()
    return render(request, 'acervo/detalhe.html', {'item': item, 'movimentacoes': movimentacoes})


@login_required
def editar(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item, usuario=request.user)
        if form.is_valid():
            try:
                form.save()
            except (ValidationError, IntegrityError):
                form.add_error(None, 'Dados invalidos ou conflito. Recarregue e confira os campos.')
                return render(request, 'acervo/editar.html', {'form': form, 'item': item})
            messages.success(request, f'{item.titulo} foi atualizado.')
            return redirect('acervo:detalhe', pk=item.pk)
    else:
        form = ItemForm(instance=item)

    return render(request, 'acervo/editar.html', {'form': form, 'item': item})


@login_required
def excluir(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == 'POST':
        titulo = item.titulo
        try:
            excluir_exemplar(item, request.user)
        except ValidationError as exc:
            messages.error(request, str(exc))
            return redirect('acervo:detalhe', pk=item.pk)
        messages.success(request, f'{titulo} foi removido do acervo.')
        return redirect('acervo:lista')

    return render(request, 'acervo/excluir.html', {'item': item})
