from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User
from usuarios.models import Perfil
from acervo.models import Produto, Categoria


class SelectionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('selector')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.category = Categoria.objects.create(nome='Rock')

    @patch('integracoes.views.pesquisar')
    def test_ambiguous_results_require_selection_and_confirmation(self, search):
        row = {'titulo': 'Album', 'tipo': 'CD', 'artista_diretor': 'Band', 'ean': '', 'ano': 2001,
               'identificadores': {'musicbrainz_release_id': '12345678-1234-1234-1234-123456789abc'}, 'metadados': {}, 'origem': 'MusicBrainz'}
        search.return_value = [row, dict(row, titulo='Another edition')]
        self.assertEqual(self.client.get('/acervo/metadados/?q=Album&fonte=musicbrainz').status_code, 200)
        self.assertEqual(Produto.objects.count(), 0)
        key = next(iter(self.client.session['metadados_escolhas']))
        self.assertEqual(self.client.post('/acervo/metadados/', {'escolha': key}).status_code, 200)
        self.assertEqual(Produto.objects.count(), 0)
        response = self.client.post('/acervo/metadados/', {'escolha': key, 'acao': 'salvar',
            'titulo': 'Album', 'tipo': 'CD', 'artista_diretor': 'Band', 'categoria': self.category.pk, 'ano': '2001'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Produto.objects.get().origem, 'MusicBrainz')

    def test_forged_selection_rejected(self):
        self.client.post('/acervo/metadados/', {'escolha': 'invented', 'acao': 'salvar'})
        self.assertEqual(Produto.objects.count(), 0)
