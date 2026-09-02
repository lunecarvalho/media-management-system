from django.shortcuts import render

from acervo.models import Item


def codigo_barras(request):
    codigo = request.GET.get('codigo', '').strip()
    item = None
    if codigo:
        item = Item.objects.select_related('categoria').filter(codigo_barras=codigo).first()
    return render(request, 'codigo_barras.html', {'codigo': codigo, 'item': item})


def configuracoes(request):
    return render(request, 'configuracoes.html')
