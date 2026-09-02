from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from movimentacoes.models import Movimentacao

from .forms import ItemForm
from .models import Categoria, Item


def lista(request):
    consulta = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    status = request.GET.get('status', '')

    itens = Item.objects.select_related('categoria').all()
    if consulta:
        itens = itens.filter(
            Q(titulo__icontains=consulta)
            | Q(artista_diretor__icontains=consulta)
            | Q(codigo_barras__icontains=consulta)
        )
    if tipo in dict(Item.TIPO_CHOICES):
        itens = itens.filter(tipo=tipo)
    if status in dict(Item.STATUS_CHOICES):
        itens = itens.filter(status=status)

    return render(
        request,
        'acervo/lista.html',
        {
            'itens': itens,
            'consulta': consulta,
            'tipo_atual': tipo,
            'status_atual': status,
        },
    )


@login_required
def cadastrar(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.usuario_responsavel = request.user
            item.save()
            Movimentacao.objects.create(
                item=item,
                tipo='cadastro',
                usuario=request.user,
                detalhes=f'Item cadastrado por {request.user.username}.',
            )
            messages.success(request, f'{item.titulo} foi adicionado ao acervo.')
            return redirect('acervo:lista')
    else:
        form = ItemForm()

    return render(
        request,
        'acervo/cadastrar.html',
        {'form': form, 'categorias': Categoria.objects.all()},
    )


def detalhe(request, pk):
    item = get_object_or_404(Item.objects.select_related('categoria'), pk=pk)
    movimentacoes = item.movimentacoes.select_related('usuario').all()
    return render(request, 'acervo/detalhe.html', {'item': item, 'movimentacoes': movimentacoes})


@login_required
def editar(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            Movimentacao.objects.create(
                item=item,
                tipo='edicao',
                usuario=request.user,
                detalhes=f'Item editado por {request.user.username}.',
            )
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
        item.delete()
        messages.success(request, f'{titulo} foi removido do acervo.')
        return redirect('acervo:lista')

    return render(request, 'acervo/excluir.html', {'item': item})
