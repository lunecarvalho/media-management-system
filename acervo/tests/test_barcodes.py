from django.test import TestCase
from django.contrib.auth.models import User
from usuarios.models import Perfil
from acervo.models import Produto, Exemplar, Categoria

class BarcodeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('scanner')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.product = Produto.objects.create(tipo='DVD', titulo='Matrix', artista_diretor='W', ean='789123', categoria=Categoria.objects.create(nome='Drama'))

    def test_consecutive_internal_reads(self):
        for code in ['MT1', 'MT2']:
            item = Exemplar.objects.create(produto=self.product, codigo_interno=code, usuario_responsavel=self.user)
            response = self.client.get('/codigo-barras/', {'codigo': code})
            self.assertEqual(response.context['item'].pk, item.pk)
            self.assertContains(response, 'data-barcode')
        self.assertNotContains(response, 'Exemplar MT1')

    def test_product_without_copies(self):
        response = self.client.get('/codigo-barras/', {'codigo': '789123'})
        self.assertContains(response, 'Cadastrar exemplar deste produto')
        self.assertContains(response, 'Nenhum exemplar disponível')

    def test_multiple_copies_for_ean(self):
        for code in ['MT1', 'MT2']:
            Exemplar.objects.create(produto=self.product, codigo_interno=code, usuario_responsavel=self.user)
        response = self.client.get('/codigo-barras/', {'codigo': '789123'})
        self.assertEqual(len(response.context['exemplares']), 2)
        self.assertEqual(self.client.get('/api/exemplares/codigo/789123/').json()['tipo_codigo'], 'ean')

    def test_unknown_code_and_explicit_mode(self):
        self.assertContains(self.client.get('/codigo-barras/?codigo=unknown'), 'Código desconhecido')
        Exemplar.objects.create(produto=self.product, codigo_interno='789123', usuario_responsavel=self.user)
        self.assertIsNone(self.client.get('/codigo-barras/?codigo=789123&modo=ean').context['item'])
