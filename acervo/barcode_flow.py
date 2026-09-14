"""Consulta externa opcional e pré-preenchimento temporário; nunca salva acervo."""
import re
import uuid
from urllib.parse import urlencode

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse

from integracoes.musicbrainz import pesquisar, FonteIndisponivel
from .validators import validar_codigo


def codigo_comercial(codigo, modo='auto'):
    return modo != 'interno' and bool(re.fullmatch(r'(?:[0-9]{8}|[0-9]{12}|[0-9]{13})', codigo))


def cadastro_manual_url(codigo, modo='auto'):
    return reverse('acervo:cadastrar') + '?' + urlencode({'codigo': codigo, 'modo': modo, 'origem': 'barcode'})


def validar_consulta(codigo, modo):
    validar_codigo(codigo)
    if len(codigo) > 40 or modo not in {'auto', 'interno', 'ean'}:
        raise ValidationError('Código ou modo inválido.')


def consultar_metadados(codigo, modo, usuario):
    try:
        validar_consulta(codigo, modo)
    except ValidationError:
        return {'erro': {'codigo': 'invalido', 'detalhes': 'Informe um código de até 40 caracteres, sem espaços.'}}, 400
    fallback = cadastro_manual_url(codigo, modo)
    missing = {'erro': {'codigo': 'nao_encontrado', 'detalhes':
        'Código não identificado. DVDs podem ser pesquisados por título no catálogo auxiliar; não há associação por EAN/UPC.'},
        'cadastro_url': fallback}
    if not codigo_comercial(codigo, modo):
        return missing, 404
    try:
        rows = pesquisar(ean=codigo, somente_cd=True)
    except FonteIndisponivel as exc:
        return {'erro': {'codigo': 'fonte_indisponivel', 'detalhes': str(exc)}, 'cadastro_url': fallback}, 502
    results = []
    for row in rows[:20]:
        # Não inferir Categoria a partir de gêneros nem aceitar outro identificador.
        if row.get('tipo') != 'CD' or not row.get('titulo') or (row.get('ean') and row['ean'] != codigo):
            continue
        fields = {key: row[key] for key in ('tipo', 'titulo', 'artista_diretor', 'ano',
                  'gravadora_distribuidora', 'descricao') if row.get(key) not in (None, '')}
        fields['ean'] = codigo
        token = uuid.uuid4().hex
        cache.set(f'barcode-prefill:{usuario.pk}:{token}', fields, timeout=1800)
        url = reverse('acervo:cadastrar') + '?' + urlencode({'leitura': token, 'codigo': codigo, 'modo': 'ean', 'origem': 'barcode'})
        results.append({**fields, 'cadastro_url': url})
    if not results:
        return missing, 404
    return {'tipo_codigo': 'externo', 'fonte': 'MusicBrainz', 'results': results}, 200


def dados_cadastro(request):
    """Valores iniciais, sempre sujeitos aos Forms e às permissões existentes."""
    item, product = {}, {}
    codigo = request.GET.get('codigo', '').strip()
    modo = request.GET.get('modo', 'auto')
    if codigo:
        try:
            validar_codigo(codigo)
            if len(codigo) <= 40:
                if codigo_comercial(codigo, modo) or modo == 'ean' and len(codigo) <= 20:
                    product['ean'] = codigo
                else:
                    item['codigo_interno'] = codigo
        except ValidationError:
            pass
    token = request.GET.get('leitura', '')
    expired = False
    if token:
        saved = cache.get(f'barcode-prefill:{request.user.pk}:{token}') if re.fullmatch(r'[a-f0-9]{32}', token) else None
        if saved:
            product = saved
        else:
            expired = True
    # Um produto cadastrado desde a consulta deve ser reutilizado.
    from .models import Produto
    existing = Produto.objects.filter(ean=product['ean']).first() if product.get('ean') else None
    item['produto'] = request.GET.get('produto') or (existing.pk if existing else None)
    return item, product, expired
