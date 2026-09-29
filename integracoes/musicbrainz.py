import hashlib
import uuid
from datetime import timedelta
import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from .models import LimiteAPI


class FonteIndisponivel(Exception):
    pass


def reservar_requisicao():
    LimiteAPI.objects.get_or_create(nome='musicbrainz')
    now = timezone.now()
    updated = LimiteAPI.objects.filter(nome='musicbrainz').filter(
        Q(ultima__isnull=True) | Q(ultima__lte=now - timedelta(seconds=1.1))).update(ultima=now)
    if not updated:
        raise FonteIndisponivel('Aguarde um instante antes de pesquisar novamente.')


def consultar(params):
    key = 'musicbrainz:cd-v3:' + hashlib.sha256(repr(sorted(params.items())).encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    reservar_requisicao()
    try:
        response = requests.get('https://musicbrainz.org/ws/2/release/',
            params={**params, 'fmt': 'json', 'limit': 20},
            headers={'User-Agent': settings.MUSICBRAINZ_USER_AGENT, 'Accept': 'application/json'},
            timeout=(3.05, 10), allow_redirects=False)
        if 400 <= response.status_code < 500:
            raise FonteIndisponivel('A pesquisa não pôde ser processada pelo MusicBrainz. Tente outra pesquisa.')
        if response.status_code != 200:
            raise FonteIndisponivel('MusicBrainz indisponível. Tente novamente mais tarde.')
        data = response.json()
        if not isinstance(data, dict):
            raise FonteIndisponivel('Resposta inválida da fonte externa.')
        releases = data.get('releases')
        if not isinstance(releases, list):
            raise FonteIndisponivel('Resposta inválida da fonte externa.')
        results = []
        for release in releases[:20]:
            try:
                media = release.get('media')
                # Pesquisa por format:CD pode incluir edições mistas. Só aceitar
                # edições com todos os suportes explicitamente identificados como CD.
                if not isinstance(media, list) or not media or any(
                    not isinstance(medium, dict) or medium.get('format') != 'CD' for medium in media
                ):
                    continue
                mbid = str(uuid.UUID(release['id']))
                if not isinstance(release.get('title'), str) or not release['title'].strip():
                    continue
                title = release['title'].strip()[:200]
                artist = ''.join(str(a.get('name', a.get('artist', {}).get('name', ''))) + str(a.get('joinphrase', ''))
                                 for a in release.get('artist-credit', []) if isinstance(a, dict))[:200]
                year_text = str(release.get('date', ''))[:4]
                results.append({'titulo': title, 'tipo': 'CD', 'artista_diretor': artist,
                    'ean': str(release.get('barcode', ''))[:20], 'ano': int(year_text) if year_text.isdigit() else None,
                    'descricao': str(release.get('disambiguation', ''))[:2000],
                    'gravadora_distribuidora': ', '.join(x.get('label', {}).get('name', '') for x in release.get('label-info', []))[:200],
                    'identificadores': {'musicbrainz_release_id': mbid}, 'origem': 'MusicBrainz',
                    'metadados': {'barcode_musicbrainz': str(release.get('barcode') or '')[:20],
                                  'data': release.get('date', ''),
                                  'catalogos': [x['catalog-number'] for x in release.get('label-info', []) if x.get('catalog-number')],
                                  'pais': release.get('country', ''), 'status': release.get('status', ''),
                                  'formatos': [medium['format'] for medium in media]}})
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        cache.set(key, results, timeout=3600)
        return results
    except requests.Timeout as exc:
        raise FonteIndisponivel('O MusicBrainz demorou para responder. Tente novamente ou continue manualmente.') from exc
    except (requests.RequestException, ValueError) as exc:
        raise FonteIndisponivel('Não foi possível consultar o MusicBrainz.') from exc


def pesquisar(texto='', artista='', ean='', somente_cd=True):
    def quoted(value):
        # Lucene: restringir operadores para não permitir consultas arbitrárias.
        return '"' + ''.join(c for c in value[:200] if c.isalnum() or c in ' -_.') + '"'
    parts = []
    if texto.strip(): parts.append('release:' + quoted(texto))
    if artista.strip(): parts.append('artist:' + quoted(artista))
    if ean.strip(): parts.append('barcode:' + quoted(ean))
    if not parts:
        return []
    # O parâmetro permanece por compatibilidade; esta fonte fornece apenas CDs.
    parts.append('format:CD')
    results = consultar({'query': ' AND '.join(parts)})
    return [row for row in results if row['ean'] == ean.strip()] if ean.strip() else results
