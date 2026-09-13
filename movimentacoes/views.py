from config.pagination import paginar
from django.db.models import Q
from django.shortcuts import render

from .models import Movimentacao


def lista(request):
    consulta = request.GET.get('q', '').strip()
    movimentacoes = Movimentacao.objects.select_related('item', 'usuario').all()
    if consulta:
        movimentacoes = movimentacoes.filter(
            Q(item__produto__titulo__icontains=consulta)
            | Q(item__codigo_interno__icontains=consulta)
            | Q(usuario__username__icontains=consulta)
        )
    movimentacoes = paginar(request, movimentacoes)
    return render(
        request,
        'movimentacoes/lista.html',
        {'movimentacoes': movimentacoes, 'page_obj': movimentacoes, 'consulta': consulta},
    )
