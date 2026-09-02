from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect, render

from acervo.models import Categoria


def lista(request):
    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        if nome:
            categoria, criada = Categoria.objects.get_or_create(
                nome=nome,
                defaults={'descricao': descricao},
            )
            if criada:
                messages.success(request, f'Categoria {categoria.nome} criada.')
            else:
                messages.warning(request, 'Essa categoria já existe.')
        else:
            messages.error(request, 'Informe o nome da categoria.')
        return redirect('categorias:lista')

    categorias = Categoria.objects.annotate(total_itens=Count('item')).order_by('nome')
    return render(request, 'categorias/lista.html', {'categorias': categorias})
