from .models import Exemplar, Produto


def localizar(codigo, modo='auto'):
    codigo = codigo.strip()
    if not codigo:
        return None, None
    if modo != 'ean':
        exemplar = Exemplar.objects.select_related('produto__categoria').filter(codigo_interno=codigo).first()
        if exemplar:
            return exemplar, exemplar.produto
    if modo != 'interno':
        return None, Produto.objects.select_related('categoria').filter(ean=codigo).first()
    return None, None
