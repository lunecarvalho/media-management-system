"""Catálogo auxiliar local. Nunca associa EAN de DVD por inferência."""
import ast
import csv
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from .models import FilmeReferencia

SOURCE = 'Kaggle:rounakbanik/the-movies-dataset'


def names(value):
    if not value:
        return []
    if len(value) > 30000:
        raise ValueError('Campo composto muito grande')
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list) or any(not isinstance(v, dict) for v in parsed):
        raise ValueError('Lista de metadados inválida')
    return [str(v.get('name', ''))[:200] for v in parsed[:100]]


def importar(path, batch_size=500):
    report = {'processados': 0, 'importados': 0, 'ignorados': 0, 'invalidos': 0}
    batch = []

    def flush():
        if not batch: return
        unique = {}
        for film in batch:
            if film.tmdb_id in unique:
                report['ignorados'] += 1
            else:
                unique[film.tmdb_id] = film
        with transaction.atomic():
            existing = set(FilmeReferencia.objects.filter(tmdb_id__in=unique).values_list('tmdb_id', flat=True))
            new = [film for key, film in unique.items() if key not in existing]
            FilmeReferencia.objects.bulk_create(new, batch_size=batch_size)
            report['importados'] += len(new)
            report['ignorados'] += len(existing)
        batch.clear()

    with open(path, encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not {'id', 'title'} <= set(reader.fieldnames):
            raise ValueError('CSV precisa das colunas id e title.')
        for raw in reader:
            report['processados'] += 1
            try:
                if None in raw:
                    raise ValueError('Colunas excedentes')
                released = raw.get('release_date', '')
                year = date.fromisoformat(released).year if released else None
                film = FilmeReferencia(tmdb_id=int(raw['id']), titulo=raw['title'],
                    titulo_original=raw.get('original_title') or raw['title'], ano=year,
                    imdb_id=raw.get('imdb_id') or '', descricao=raw.get('overview') or '',
                    metadados={'generos': names(raw.get('genres')), 'idioma': raw.get('original_language') or '',
                    'paises': names(raw.get('production_countries')), 'produtoras': names(raw.get('production_companies'))})
                film.full_clean(validate_unique=False)
                batch.append(film)
                if len(batch) >= batch_size: flush()
            except (ValidationError, ValueError, TypeError, SyntaxError):
                report['invalidos'] += 1
        flush()
    return report


def pesquisar(texto='', ano=None, identificador=''):
    films = FilmeReferencia.objects.all()
    if identificador:
        films = films.filter(Q(imdb_id=identificador) | Q(tmdb_id=int(identificador) if identificador.isdigit() else -1))
    elif texto.strip():
        films = films.filter(Q(titulo__icontains=texto.strip()[:200]) | Q(titulo_original__icontains=texto.strip()[:200]))
    else:
        return []
    if ano: films = films.filter(ano=ano)
    return [{'titulo': f.titulo, 'tipo': 'DVD', 'artista_diretor': '', 'ean': '', 'ano': f.ano,
             'descricao': f.descricao, 'gravadora_distribuidora': ', '.join(f.metadados.get('produtoras', []))[:200],
             'identificadores': {'tmdb_id': str(f.tmdb_id), 'imdb_id': f.imdb_id},
             'origem': SOURCE, 'metadados': {**f.metadados, 'titulo_original': f.titulo_original}}
            for f in films.order_by('titulo', 'tmdb_id')[:20]]
