import csv
import io
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import Produto, Exemplar, Categoria, ImportacaoCSV
from .services import salvar_exemplar, salvar_produto

MAX_BYTES = 1024 * 1024
MAX_ROWS = 500
HEADERS = {'codigo_interno', 'ean', 'tipo', 'titulo', 'artista_diretor', 'categoria', 'ano',
           'gravadora_distribuidora', 'descricao', 'estado_conservacao', 'preco', 'localizacao'}


def ler(content):
    if len(content.encode('utf-8')) > MAX_BYTES:
        raise ValidationError('CSV excede 1 MiB.')
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), delimiter=',')
    if not reader.fieldnames or 'codigo_interno' not in reader.fieldnames or not set(reader.fieldnames) <= HEADERS:
        raise ValidationError('Cabeçalho inválido. Utilize o CSV de exemplo.')
    if len(reader.fieldnames) != len(set(reader.fieldnames)):
        raise ValidationError('Cabeçalho contém colunas duplicadas.')
    rows = []
    seen_codes = set()
    seen_products = {}
    for number, raw in enumerate(reader, 2):
        if len(rows) >= MAX_ROWS:
            raise ValidationError('Limite de 500 linhas por importação.')
        result = {'linha': number, 'dados': raw, 'situacao': 'novo', 'erro': ''}
        try:
            if None in raw or any(v is None for v in raw.values()):
                raise ValidationError('Quantidade de colunas inválida.')
            data = {k: v.strip() for k, v in raw.items()}
            result['dados'] = data
            code = data.get('codigo_interno', '')
            if code in seen_codes:
                raise ValidationError('Código interno repetido dentro do arquivo.')
            seen_codes.add(code)
            ean = data.get('ean') or None
            product = Produto.objects.filter(ean=ean).first() if ean else None
            if product:
                for field in ('titulo', 'tipo', 'artista_diretor'):
                    if data.get(field) and data[field] != getattr(product, field):
                        raise ValidationError('EAN existente com metadados divergentes; revise a associação.')
            else:
                category = Categoria.objects.filter(nome=data.get('categoria', '')).first()
                if not category:
                    raise ValidationError('Categoria deve existir antes da importação.')
                product = Produto(tipo=data.get('tipo', ''), titulo=data.get('titulo', ''),
                    artista_diretor=data.get('artista_diretor', ''), categoria=category, ean=ean,
                    ano=int(data['ano']) if data.get('ano') else None,
                    gravadora_distribuidora=data.get('gravadora_distribuidora', ''), descricao=data.get('descricao', ''))
                product.full_clean()
            signature = (product.tipo, product.titulo, product.artista_diretor, product.categoria_id, product.ano)
            if ean and ean in seen_products and seen_products[ean] != signature:
                raise ValidationError('EAN repetido com dados divergentes no arquivo.')
            if ean: seen_products[ean] = signature
            price = Decimal(data['preco']) if data.get('preco') else None
            copy = Exemplar(produto=product, codigo_interno=code, preco=price,
                estado_conservacao=data.get('estado_conservacao') or 'bom', localizacao=data.get('localizacao', ''))
            copy.full_clean(exclude=['produto', 'usuario_responsavel'], validate_unique=False)
            existing = Exemplar.objects.select_related('produto').filter(codigo_interno=code).first()
            if existing:
                same_product = existing.produto_id == product.pk if product.pk else (
                    not existing.produto.ean and existing.produto.titulo == product.titulo and
                    existing.produto.artista_diretor == product.artista_diretor and existing.produto.tipo == product.tipo)
                if not same_product or existing.preco != price or existing.localizacao != copy.localizacao or existing.estado_conservacao != copy.estado_conservacao:
                    raise ValidationError('Código interno existente com dados diferentes; nenhuma atualização automática.')
                result['situacao'] = 'ignorado'
            result['_produto'] = product
            result['_exemplar'] = copy
        except (ValidationError, ValueError, InvalidOperation) as exc:
            result['situacao'] = 'invalido'
            result['erro'] = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'Valor numérico inválido.'
        rows.append(result)
    if not rows:
        raise ValidationError('CSV vazio.')
    return rows


def resumo(rows):
    return {state: sum(r['situacao'] == state for r in rows) for state in ('novo', 'ignorado', 'invalido')}


@transaction.atomic
def confirmar(batch_id, user):
    from django.utils import timezone
    from datetime import timedelta
    batch = ImportacaoCSV.objects.select_for_update().get(pk=batch_id, usuario=user)
    if batch.confirmado:
        return batch.resultado
    if timezone.now() - batch.criado > timedelta(hours=24):
        raise ValidationError('Prévia expirada. Envie o arquivo novamente.')
    rows = ler(batch.conteudo)
    report = resumo(rows)
    if report['invalido']:
        raise ValidationError('Há linhas inválidas. Corrija o arquivo antes de confirmar.')
    products = {}
    for row in rows:
        if row['situacao'] != 'novo':
            continue
        product, copy = row['_produto'], row['_exemplar']
        if product.ean:
            product = products.get(product.ean) or Produto.objects.filter(ean=product.ean).first() or product
        if not product.pk:
            product = salvar_produto(product, user)
        if product.ean: products[product.ean] = product
        salvar_exemplar(usuario=user, dados={'produto': product, 'codigo_interno': copy.codigo_interno,
            'preco': copy.preco, 'estado_conservacao': copy.estado_conservacao, 'localizacao': copy.localizacao})
    report['importado'] = report.pop('novo')
    batch.confirmado = True
    batch.resultado = report
    batch.save(update_fields=['confirmado', 'resultado'])
    return report
