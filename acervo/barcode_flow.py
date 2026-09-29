"""Consulta de DVDs locais e CDs externos; pré-preenchimento em sessão, sem salvar acervo."""
import re
import uuid
import time
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.urls import reverse

from integracoes.musicbrainz import pesquisar, FonteIndisponivel
from integracoes.dvd_dataset import pesquisar as pesquisar_dvds, SOURCE as DVD_SOURCE
from .validators import validar_codigo


def codigo_comercial(codigo, modo='auto'):
    return modo != 'interno' and bool(re.fullmatch(r'(?:[0-9]{8}|[0-9]{12}|[0-9]{13})', codigo))


def cadastro_manual_url(codigo, modo='auto'):
    return reverse('acervo:cadastrar') + '?' + urlencode({'codigo': codigo, 'modo': modo, 'origem': 'barcode'})


def validar_consulta(codigo, modo):
    validar_codigo(codigo)
    if len(codigo) > 40 or modo not in {'auto', 'interno', 'ean'}:
        raise ValidationError('Código ou modo inválido.')


def consultar_metadados(codigo, modo, request, externa=True):
    try:
        validar_consulta(codigo, modo)
    except ValidationError:
        return {'erro': {'codigo': 'invalido', 'detalhes': 'Informe um código de até 40 caracteres, sem espaços.'}}, 400
    fallback = cadastro_manual_url(codigo, modo)
    missing = {'erro': {'codigo': 'nao_encontrado', 'detalhes':
        'Nenhum produto encontrado nas fontes consultadas. Continue com o cadastro manual.'},
        'cadastro_url': fallback, 'metadados_disponiveis': codigo_comercial(codigo, modo) and not externa}
    if not codigo_comercial(codigo, modo):
        return missing, 404
    missing['busca_cd_url'] = reverse('acervo:buscar_cd') + '?' + urlencode({'codigo': codigo})
    rows = pesquisar_dvds(ean=codigo)
    source, media_type = DVD_SOURCE, 'DVD'
    if not rows:
        if not externa:
            return missing, 404
        source, media_type = 'MusicBrainz', 'CD'
        try:
            rows = pesquisar(ean=codigo, somente_cd=True)
        except FonteIndisponivel as exc:
            return {'erro': {'codigo': 'fonte_indisponivel', 'detalhes': str(exc)}, 'cadastro_url': fallback, 'busca_cd_url': missing['busca_cd_url']}, 502
    results = []
    for row in rows[:20]:
        # Não inferir Categoria a partir de gêneros nem aceitar outro identificador.
        if row.get('tipo') != media_type or not row.get('titulo') or (row.get('ean') and row['ean'] != codigo):
            continue
        fields = {key: row[key] for key in ('tipo', 'titulo', 'artista_diretor', 'ano',
                  'gravadora_distribuidora', 'descricao') if row.get(key) not in (None, '')}
        fields['ean'] = codigo
        fields.update(origem=source, identificadores=row.get('identificadores', {}), metadados=row.get('metadados', {}))
        url = guardar_prefill(request, fields, codigo)
        results.append({**fields, 'cadastro_url': url})
    if not results:
        return missing, 404
    return {'tipo_codigo': 'externo', 'fonte': source, 'results': results}, 200


def guardar_prefill(request, fields, codigo):
    """Transporta somente dados obtidos no servidor, na sessão compartilhada."""
    token = uuid.uuid4().hex
    entries = {key: value for key, value in request.session.get('barcode_prefill', {}).items()
               if value['expira'] > time.time()}
    entries[token] = {'usuario': request.user.pk, 'expira': time.time() + 1800, 'dados': fields}
    request.session['barcode_prefill'] = dict(list(entries.items())[-40:])
    return reverse('acervo:cadastrar') + '?' + urlencode(
        {'leitura': token, 'codigo': codigo, 'modo': 'ean', 'origem': 'barcode'})


def metadados_selecionados(request):
    token = request.GET.get('leitura', '')
    entry = request.session.get('barcode_prefill', {}).get(token) if re.fullmatch(r'[a-f0-9]{32}', token) else None
    if entry and entry['usuario'] == request.user.pk and entry['expira'] > time.time():
        return entry['dados']
    return None


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
        saved = metadados_selecionados(request)
        if saved:
            product = saved
        else:
            expired = True
    # Um produto cadastrado desde a consulta deve ser reutilizado.
    from .models import Produto
    existing = Produto.objects.filter(ean=product['ean']).first() if product.get('ean') else None
    item['produto'] = request.GET.get('produto') or (existing.pk if existing else None)
    return item, product, expired
