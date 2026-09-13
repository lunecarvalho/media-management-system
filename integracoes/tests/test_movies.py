import csv
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase
from django.core.management import call_command
from integracoes.models import FilmeReferencia
from integracoes.movies_dataset import importar, pesquisar
from acervo.models import Produto

class MoviesTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'movies.csv'
        with self.path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['id', 'title', 'original_title', 'release_date', 'imdb_id', 'genres'])
            writer.writeheader()
            writer.writerow({'id': '1', 'title': 'Matrix', 'original_title': 'The Matrix', 'release_date': '1999-03-31', 'imdb_id': 'tt0133093', 'genres': "[{'id': 1, 'name': 'Action'}]"})
            writer.writerow({'id': '2', 'title': 'Matrix', 'release_date': '2000-01-01'})
            writer.writerow({'id': 'bad', 'title': 'Invalid'})

    def test_chunks_and_idempotent_import(self):
        result = importar(self.path, batch_size=1)
        self.assertEqual(result, {'processados': 3, 'importados': 2, 'ignorados': 0, 'invalidos': 1})
        self.assertEqual(importar(self.path)['ignorados'], 2)
        self.assertEqual(Produto.objects.count(), 0)

    def test_search_by_original_title_year_and_ids(self):
        importar(self.path)
        self.assertEqual(len(pesquisar('Matrix')), 2)
        self.assertEqual(len(pesquisar('The Matrix', 1999)), 1)
        self.assertEqual(pesquisar(identificador='tt0133093')[0]['ean'], '')
        self.assertEqual(pesquisar(identificador='1')[0]['metadados']['generos'], ['Action'])

    def test_optional_dataset_and_command_report(self):
        self.assertEqual(pesquisar('Matrix'), [])
        output = io.StringIO()
        call_command('importar_filmes', arquivo=str(self.path), lote=1, stdout=output)
        self.assertEqual(json.loads(output.getvalue())['invalidos'], 1)
