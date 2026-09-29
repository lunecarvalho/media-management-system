import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from acervo.models import Produto, Exemplar
from integracoes.dvd_dataset import importar, pesquisar, SOURCE
from integracoes.models import FilmeReferencia


class DVDImportTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'dvds.sql'

    def write(self, content):
        self.path.write_text(content, encoding='utf-8')
        return self.path

    def test_import_and_repeat_preserve_codes_and_metadata(self):
        self.write("INSERT INTO FILMES VALUES ('0012345678905', 'D''Artagnan; -- filme', 'Diretor, Diretora', 2001);\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Lana Wachowski, Lilly Wachowski', 1999);")
        first = importar(self.path)
        self.assertEqual((first['criados'], first['invalidos']), (2, 0))
        self.assertEqual(importar(self.path)['ignorados'], 2)
        self.assertEqual(FilmeReferencia.objects.count(), 2)
        row = pesquisar(ean='0012345678905')[0]
        self.assertEqual(row['tipo'], 'DVD')
        self.assertEqual(row['titulo'], "D'Artagnan; -- filme")
        self.assertEqual(row['artista_diretor'], 'Diretor, Diretora')
        self.assertEqual(row['ano'], 2001)
        self.assertEqual(row['ean'], '0012345678905')
        self.assertEqual(row['origem'], SOURCE)
        self.assertEqual(pesquisar(ean='0000000000000'), [])
        self.assertFalse(Produto.objects.exists())
        self.assertFalse(Exemplar.objects.exists())

    def test_update_existing_reference_without_changing_catalog(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);")
        importar(self.path)
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'Matrix revisado', 'Diretores', 2000);")
        self.assertEqual(importar(self.path)['atualizados'], 1)
        self.assertEqual(FilmeReferencia.objects.count(), 1)
        row = pesquisar(ean='7892110019392')[0]
        self.assertEqual((row['titulo'], row['artista_diretor'], row['ano']), ('Matrix revisado', 'Diretores', 2000))

    def test_invalid_entries_and_duplicate_conflict_are_reported(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'Outro', 'Diretor', 2000);\n"
                   "INSERT INTO FILMES VALUES ('abc', 'Filme', 'Diretor', 2000);\n"
                   "INSERT INTO FILMES VALUES (7892110019393, '', 'Diretor', 2000);\n"
                   "INSERT INTO FILMES VALUES (7892110019394, 'Filme', NULL, 2000);\n"
                   "INSERT INTO FILMES VALUES (7892110019395, 'Filme', 'Diretor', -1);\n"
                   "INSERT INTO FILMES VALUES (7892110019396, 'Filme', 'Diretor', 'abc');\n"
                   "INSERT INTO FILMES VALUES (7892110019397, 'Filme', 'Diretor', 9999);\n"
                   "INSERT INTO FILMES VALUES (broken);")
        report = importar(self.path)
        self.assertEqual((report['criados'], report['ignorados'], report['invalidos']), (1, 1, 8))
        self.assertEqual(len(report['erros']), 8)
        self.assertEqual(report['erros'][0]['linha'], 3)
        self.assertEqual(FilmeReferencia.objects.get().titulo, 'MATRIX')

    def test_sql_is_never_executed_and_unsupported_statements_abort_before_writes(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'Filme', 'Diretor', 2000);\nDROP TABLE acervo_produto;")
        with self.assertRaises(ValueError):
            importar(self.path)
        self.assertFalse(FilmeReferencia.objects.exists())
        self.assertEqual(Produto.objects.count(), 0)
        with self.assertRaises(CommandError):
            call_command('importar_filmes', arquivo=str(self.path))

    def test_header_command_defaults_and_counts(self):
        self.write("-- create\nCREATE TABLE FILMES (\nEanId BIGINT PRIMARY KEY,\ntit TEXT NOT NULL,\n"
                   "diretor TEXT NOT NULL,\nano INTEGER NOT NULL\n);\n-- insert\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);")
        for expected in ({'criados': 1, 'ignorados': 0}, {'criados': 0, 'ignorados': 1}):
            output = io.StringIO()
            with self.settings(DVD_DATASET_PATH=str(self.path)):
                call_command('importar_filmes', stdout=output)
            report = json.loads(output.getvalue())
            for key, value in expected.items():
                self.assertEqual(report[key], value)
            self.assertEqual(report['atualizados'], 0)
            self.assertEqual(report['invalidos'], 0)

    def test_legacy_rows_are_preserved_but_not_identified_as_dvds(self):
        legacy = FilmeReferencia.objects.create(tmdb_id=1, titulo='Legado', titulo_original='Legado',
            origem='Kaggle:rounakbanik/the-movies-dataset')
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'Legado', 'Diretor', 1999);")
        importar(self.path)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.ean)
        self.assertEqual(FilmeReferencia.objects.count(), 2)
        self.assertEqual(len(pesquisar('Legado')), 1)

    def test_database_failure_rolls_back_whole_import(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'Filme', 'Diretor', 2000);\n"
                   "INSERT INTO FILMES VALUES (7892110019393, 'Outro', 'Diretor', 2001);")
        original = FilmeReferencia.objects.update_or_create
        def fail_second(**kwargs):
            if kwargs['ean'] == '7892110019393':
                raise RuntimeError('simulated failure')
            return original(**kwargs)
        with patch.object(FilmeReferencia.objects, 'update_or_create', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                importar(self.path)
        self.assertFalse(FilmeReferencia.objects.exists())
