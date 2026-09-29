"""Importação declarativa do SQL do grupo. Nenhum comando SQL é executado."""
import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .models import FilmeReferencia

SOURCE = 'Base de DVDs do grupo'
SQL_HEADER = re.compile(
    r'CREATE\s+TABLE\s+FILMES\s*\(\s*EanId\s+BIGINT\s+PRIMARY\s+KEY\s*,\s*'
    r'tit\s+TEXT\s+NOT\s+NULL\s*,\s*diretor\s+TEXT\s+NOT\s+NULL\s*,\s*'
    r'ano\s+INTEGER\s+NOT\s+NULL\s*\)\s*;', re.I)
LITERAL = r"(?:'(?:[^']|'')*'|[+-]?[0-9]+|NULL)"
INSERT = re.compile(
    r'INSERT\s+INTO\s+FILMES\s+(?:\(\s*EanId\s*,\s*tit\s*,\s*diretor\s*,\s*ano\s*\)\s*)?'
    r'VALUES\s*\(\s*(' + LITERAL + r')\s*,\s*(' + LITERAL + r')\s*,\s*('
    + LITERAL + r')\s*,\s*(' + LITERAL + r')\s*\)\s*;', re.I)


def valor(literal):
    if literal.upper() == 'NULL':
        return None
    return literal[1:-1].replace("''", "'").strip() if literal.startswith("'") else literal


def ler(path):
    """Aceita o formato inspecionado: cabeçalho conhecido e um INSERT por linha."""
    path = Path(path)
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('SQL excede 16 MiB.')
    content = path.read_text(encoding='utf-8-sig')
    content = re.sub(r'^[ \t]*--[^\n]*', '', content, flags=re.M)
    # Preserva a numeração das linhas ao descartar apenas o DDL conhecido.
    content = SQL_HEADER.sub(lambda match: '\n' * match[0].count('\n'), content, count=1)
    rows = []
    for line, statement in enumerate(content.splitlines(), 1):
        statement = statement.strip()
        if not statement:
            continue
        if not re.match(r'INSERT\s+INTO\s+FILMES\b', statement, re.I):
            raise ValueError(f'Linha {line}: comando não suportado. O arquivo não será executado.')
        match = INSERT.fullmatch(statement)
        rows.append((line, tuple(valor(value) for value in match.groups()) if match else None))
    if not rows:
        raise ValueError('Nenhum INSERT de FILMES encontrado.')
    return rows


@transaction.atomic
def importar(path):
    rows = ler(path)  # Validar a estrutura inteira antes de gravar.
    report = dict(processados=0, criados=0, atualizados=0, ignorados=0, invalidos=0, erros=[])
    seen = {}
    for line, values in rows:
        report['processados'] += 1
        try:
            if values is None:
                raise ValidationError('INSERT inválido; utilize quatro valores e uma linha por registro.')
            ean, title, director, year = values
            if not ean or not title or not director or year is None:
                raise ValidationError('EAN, título, diretor e ano são obrigatórios.')
            if len(title) > 200:
                raise ValidationError('Título excede os 200 caracteres aceitos pelo cadastro de Produto.')
            film = FilmeReferencia(ean=ean, titulo=title, titulo_original=title,
                                   diretor=director, ano=int(year), origem=SOURCE)
            film.full_clean(validate_unique=False)
            signature = (title, director, film.ano)
            if ean in seen:
                if seen[ean] != signature:
                    raise ValidationError('EAN repetido com dados divergentes no arquivo; primeira ocorrência mantida.')
                report['ignorados'] += 1
                continue
            seen[ean] = signature
            current = FilmeReferencia.objects.select_for_update().filter(ean=ean).first()
            if current and current.origem != SOURCE:
                raise ValidationError('EAN pertence a outra fonte; revisão manual necessária.')
            fields = dict(titulo=title, titulo_original=title, diretor=director, ano=film.ano, origem=SOURCE)
            if current and all(getattr(current, key) == value for key, value in fields.items()):
                report['ignorados'] += 1
            else:
                _, created = FilmeReferencia.objects.update_or_create(ean=ean, defaults=fields)
                report['criados' if created else 'atualizados'] += 1
        except (ValidationError, ValueError, TypeError) as exc:
            report['invalidos'] += 1
            report['erros'].append({'linha': line, 'erro': '; '.join(exc.messages)
                if isinstance(exc, ValidationError) else 'Ano inválido.'})
    return report


def pesquisar(texto='', ano=None, ean=''):
    films = FilmeReferencia.objects.filter(origem=SOURCE, ean__isnull=False)
    if ean:
        films = films.filter(ean=ean.strip())
    elif texto.strip():
        films = films.filter(Q(titulo__icontains=texto.strip()[:200]) | Q(titulo_original__icontains=texto.strip()[:200]))
    else:
        return []
    if ano:
        films = films.filter(ano=ano)
    return [{'titulo': film.titulo, 'tipo': 'DVD', 'artista_diretor': film.diretor,
             'ean': film.ean, 'ano': film.ano, 'origem': SOURCE,
             'identificadores': {'dvd_ean': film.ean}, 'metadados': {},
             'descricao': '', 'gravadora_distribuidora': ''}
            for film in films.order_by('titulo', 'ean')[:20]]
