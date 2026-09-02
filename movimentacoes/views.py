from django.db.models import Q
from django.shortcuts import render

from .models import Movimentacao


def lista(request):
    consulta = request.GET.get('q', '').strip()
    movimentacoes = Movimentacao.objects.select_related('item', 'usuario').all()
    if consulta:
        movimentacoes = movimentacoes.filter(
            Q(item__titulo__icontains=consulta)
            | Q(item__codigo_barras__icontains=consulta)
            | Q(usuario__username__icontains=consulta)
        )
    return render(
        request,
        'movimentacoes/lista.html',
        {'movimentacoes': movimentacoes, 'consulta': consulta},
    )
