import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import TestCase

from acervo.models import Produto, Exemplar
from integracoes.dvd_dataset import importar, ler, pesquisar, preflight, simular, SOURCE
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

    def test_strict_import_rolls_back_validation_errors(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'Filme', 'Diretor', 2000);\n"
                   "INSERT INTO FILMES VALUES (7892110019393, 'Inválido', '', 2001);")
        with self.assertRaises(ValidationError):
            importar(self.path, strict=True)
        self.assertFalse(FilmeReferencia.objects.exists())

    def test_preflight_reports_database_conflicts_without_writing(self):
        FilmeReferencia.objects.create(
            ean='7892110019392', titulo='Outra', titulo_original='Outra',
            diretor='Diretor', ano=2000, origem='Outra fonte',
        )
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);")
        from django.db import connection
        real_cursor = connection.cursor
        calls = {'count': 0}

        class IdentityCursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def execute(self, query):
                self.query = query

            def fetchone(self):
                return ('mediatrack', 'public')

        def cursor_factory(*args, **kwargs):
            calls['count'] += 1
            return IdentityCursor() if calls['count'] == 1 else real_cursor(*args, **kwargs)

        with patch('integracoes.dvd_dataset.connection.cursor', side_effect=cursor_factory):
            report = preflight(self.path, expected_database='mediatrack')
        self.assertEqual(report['conflitos_outra_origem'], ['7892110019392'])
        self.assertEqual(FilmeReferencia.objects.count(), 1)

    def test_confirmed_command_requires_confirmation_and_does_not_write_when_cancelled(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);")
        with patch('integracoes.management.commands.importar_filmes.preflight',
                   return_value={
                       'processados': 1, 'validos': 1, 'invalidos': 0,
                       'duplicados_iguais': 0, 'duplicados_conflitantes': 0,
                       'conflitos_outra_origem': [], 'existentes_mesma_origem': [],
                       'banco': {'database': 'mediatrack', 'schema': 'public'},
                   }), patch('builtins.input', return_value='CANCELAR'):
            with self.assertRaises(CommandError):
                call_command(
                    'importar_filmes', arquivo=str(self.path),
                    confirmar=True, confirmar_banco='mediatrack',
                )
        self.assertFalse(FilmeReferencia.objects.exists())

    def test_dry_run_reconciles_categories_without_writing(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);\n"
                   "INSERT INTO FILMES VALUES (7892110019392, 'Outra', 'Diretor', 1999);\n"
                   "INSERT INTO FILMES VALUES (7892110019393, 'Válido', 'Diretor', 2000);")
        existing = FilmeReferencia.objects.create(
            ean='7892110019394', titulo='Existente', titulo_original='Existente',
            diretor='Diretor', ano=2000,
        )

        report = simular(self.path)

        self.assertEqual(report['processados'], 4)
        self.assertEqual(
            {
                key: report[key]
                for key in (
                    'validos',
                    'invalidos',
                    'duplicados_iguais',
                    'duplicados_conflitantes',
                )
            },
            {
                'validos': 2,
                'invalidos': 0,
                'duplicados_iguais': 1,
                'duplicados_conflitantes': 1,
            },
        )
        self.assertEqual(report['conflitos_banco'], 'nao_verificados')
        self.assertEqual(sum(report['categorias'].values()), report['processados'])
        self.assertEqual(FilmeReferencia.objects.count(), 1)
        existing.refresh_from_db()
        self.assertEqual(existing.titulo, 'Existente')

    def test_dry_run_reports_validation_errors_without_database_access(self):
        long_title = 'x' * 201
        self.write(
            "INSERT INTO FILMES VALUES ('abc', 'EAN inválido', 'Diretor', 2000);\n"
            "INSERT INTO FILMES VALUES (7892110019393, 'Ano inválido', 'Diretor', 0);\n"
            f"INSERT INTO FILMES VALUES (7892110019394, '{long_title}', 'Diretor', 2000);\n"
            "INSERT INTO FILMES VALUES (broken);"
        )

        with patch.object(
            FilmeReferencia.objects,
            'filter',
            side_effect=AssertionError('dry-run consultou o banco'),
        ), patch.object(
            FilmeReferencia.objects,
            'select_for_update',
            side_effect=AssertionError('dry-run consultou o banco'),
        ), patch.object(
            FilmeReferencia.objects,
            'update_or_create',
            side_effect=AssertionError('dry-run gravou'),
        ):
            report = simular(self.path)

        self.assertEqual(report['processados'], 4)
        self.assertEqual(report['invalidos'], 4)
        self.assertEqual(sum(report['categorias'].values()), report['processados'])
        self.assertFalse(FilmeReferencia.objects.exists())

    def test_dry_run_command_does_not_call_persistence(self):
        self.write("INSERT INTO FILMES VALUES (7892110019392, 'MATRIX', 'Diretor', 1999);")
        with patch('integracoes.dvd_dataset.FilmeReferencia.objects.update_or_create',
                   side_effect=AssertionError('dry-run gravou')):
            output = io.StringIO()
            call_command('importar_filmes', arquivo=str(self.path), dry_run=True, stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report['validos'], 1)
        self.assertFalse(FilmeReferencia.objects.exists())

    def test_real_dataset_has_reconcilable_137_records(self):
        dataset = Path(__file__).resolve().parents[2] / 'datasets' / 'bd_model-criacao.sql'
        report = simular(dataset)

        self.assertEqual(len(ler(dataset)), 137)
        self.assertEqual(report['processados'], 137)
        self.assertEqual(sum(report['categorias'].values()), 137)
        self.assertEqual(
            sum(
                report[key]
                for key in (
                    'validos',
                    'invalidos',
                    'duplicados_iguais',
                    'duplicados_conflitantes',
                )
            ),
            report['processados'],
        )
        self.assertEqual(report['conflitos_banco'], 'nao_verificados')
