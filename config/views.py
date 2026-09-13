from django.shortcuts import render

from acervo.models import Item, Produto
from django.db.models import Count, Sum, Q
from decimal import Decimal
from movimentacoes.models import Movimentacao
from django.http import JsonResponse
from django.db import connection, DatabaseError
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache


@require_safe
@never_cache
def health(request):
    """Liveness: o processo responde, independentemente do banco."""
    return JsonResponse({'status': 'ok'})


@require_safe
@never_cache
def readiness(request):
    """Readiness: dependências críticas disponíveis, sem expor detalhes."""
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except DatabaseError:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})


def dashboard(request):
    counts = Item.objects.aggregate(total=Count('pk'),
        disponivel=Count('pk', filter=Q(status='disponivel')),
        reservado=Count('pk', filter=Q(status='reservado')),
        vendido=Count('pk', filter=Q(status='vendido')))
    value = Item.objects.filter(status__in=['disponivel', 'reservado']).aggregate(valor=Sum('preco'))['valor'] or Decimal('0')
    return render(request, 'dashboard-fixed.html', {
        'indicadores': [('Produtos', Produto.objects.count()), ('Exemplares', counts['total']),
                        ('Disponíveis', counts['disponivel']), ('Reservados', counts['reservado']), ('Vendidos', counts['vendido'])],
        'valor_estoque': value,
        'recentes': Movimentacao.objects.select_related('item__produto', 'usuario')[:10],
    })


def codigo_barras(request):
    from acervo.barcodes import localizar
    from .pagination import paginar
    codigo = request.GET.get('codigo', '').strip()
    modo = request.GET.get('modo', 'auto')
    if modo not in {'auto', 'ean', 'interno'}: modo = 'auto'
    item, produto = localizar(codigo, modo)
    exemplares = paginar(request, produto.exemplares.select_related('produto').all()) if produto else None
    return render(request, 'codigo_barras.html', {'codigo': codigo, 'modo': modo, 'item': item,
        'produto': produto, 'exemplares': exemplares, 'page_obj': exemplares,
        'disponiveis': produto.exemplares.filter(status='disponivel').exists() if produto else False})


def configuracoes(request):
    return render(request, 'configuracoes.html')
