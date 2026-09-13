from pathlib import Path
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from acervo.models import Categoria, Produto, Exemplar, ImportacaoCSV
from acervo.csv_import import ler, confirmar
from usuarios.models import Perfil

class CSVTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('importer')
        Perfil.objects.create(usuario=self.user)
        Categoria.objects.create(nome='Drama')
        self.content = (Path(__file__).resolve().parents[2] / 'examples/acervo.csv').read_text()
        self.batch = ImportacaoCSV.objects.create(usuario=self.user, conteudo=self.content)

    def test_repeated_ean_and_reexecution(self):
        self.assertEqual(confirmar(self.batch.pk, self.user)['importado'], 2)
        self.assertEqual(Produto.objects.count(), 1)
        self.assertEqual(Exemplar.objects.count(), 2)
        self.assertEqual(confirmar(self.batch.pk, self.user)['importado'], 2)
        new = ImportacaoCSV.objects.create(usuario=self.user, conteudo=self.content)
        self.assertEqual(confirmar(new.pk, self.user)['ignorado'], 2)
        self.assertEqual(Exemplar.objects.count(), 2)

    def test_invalid_line_prevents_entire_import(self):
        self.batch.conteudo = self.content.replace('30.00', '-30.00')
        self.batch.save()
        with self.assertRaises(ValidationError):
            confirmar(self.batch.pk, self.user)
        self.assertEqual(Exemplar.objects.count(), 0)

    def test_duplicate_code_reported(self):
        rows = ler(self.content.replace('MT00002', 'MT00001'))
        self.assertEqual(rows[1]['situacao'], 'invalido')

    def test_upload_preview_confirmation(self):
        self.client.force_login(self.user)
        response = self.client.post('/acervo/importar/', {'arquivo': SimpleUploadedFile('items.csv', self.content.encode())})
        self.assertEqual(response.status_code, 302)
        preview = self.client.get(response.url)
        self.assertContains(preview, 'Confirmar')
        self.assertEqual(Exemplar.objects.count(), 0)
        self.assertEqual(self.client.post(response.url).status_code, 200)
        self.assertEqual(Exemplar.objects.count(), 2)

    def test_other_user_cannot_confirm(self):
        other = User.objects.create_user('other')
        Perfil.objects.create(usuario=other)
        self.client.force_login(other)
        self.assertEqual(self.client.post(f'/acervo/importar/{self.batch.pk}/').status_code, 404)
