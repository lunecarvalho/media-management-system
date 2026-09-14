from django.shortcuts import render

from acervo.models import Item, Produto
from django.db.models import Count, Sum, Q
from decimal import Decimal
from movimentacoes.models import Movimentacao
from django.http import JsonResponse
from django.db import connection, DatabaseError
from django.views.decorators.http import require_safe
from django.views.decorators.cache import never_cache
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import datetime, time, timedelta


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
    estoque = Q(status__in=['disponivel', 'reservado'])
    counts = Item.objects.aggregate(
        cds=Count('pk', filter=estoque & Q(produto__tipo='CD')),
        dvds=Count('pk', filter=estoque & Q(produto__tipo='DVD')),
        disponiveis=Count('pk', filter=Q(status='disponivel')),
        valor=Sum('preco', filter=estoque))
    now = timezone.now()
    today = timezone.localdate(now)
    first_day = today - timedelta(days=6)
    month_start = today.replace(day=1)
    start = timezone.make_aware(datetime.combine(min(first_day, month_start), time.min))
    # Eventos de venda, não o status atual da cópia. Cancelamentos não apagam o histórico.
    daily_sales = dict(Movimentacao.objects.filter(tipo='venda', data__gte=start, data__lte=now)
        .annotate(dia=TruncDate('data')).values('dia').annotate(total=Count('pk'))
        .order_by('dia').values_list('dia', 'total'))
    days = [{'data': first_day + timedelta(days=i),
             'total': daily_sales.get(first_day + timedelta(days=i), 0)} for i in range(7)]
    maximum = max((day['total'] for day in days), default=0) or 1
    for day in days:
        day['altura'] = round(day['total'] * 100 / maximum)
        day['y'] = 100 - day['altura']
    month_sales = sum(total for day, total in daily_sales.items() if day >= month_start)
    categories = list(Item.objects.filter(estoque).values('produto__categoria__nome')
        .annotate(total=Count('pk')).order_by('-total', 'produto__categoria__nome')[:4])
    value = counts['valor'] or Decimal('0')
    return render(request, 'dashboard-fixed.html', {
        'metricas': counts, 'vendidos_mes': month_sales,
        'vendas_dias': days, 'vendas_total': sum(day['total'] for day in days),
        'top_categorias': categories, 'categoria_max': categories[0]['total'] if categories else 1,
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
