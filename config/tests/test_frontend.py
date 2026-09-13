from django.test import TestCase
from django.contrib.auth.models import User
from usuarios.models import Perfil
from acervo.models import Produto, Exemplar, Categoria


class FrontendTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reader')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)

    def test_private_pages_render(self):
        for url in ('/', '/acervo/', '/categorias/', '/movimentacoes/', '/codigo-barras/', '/configuracoes/', '/acervo/cadastrar/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_layout_and_zero_price(self):
        product = Produto.objects.create(tipo='DVD', titulo='Zero', artista_diretor='Director', categoria=Categoria.objects.create(nome='Drama'))
        item = Exemplar.objects.create(produto=product, codigo_interno='MT0', preco=0, usuario_responsavel=self.user)
        response = self.client.get(f'/acervo/item/{item.pk}/')
        self.assertContains(response, 'R$ 0,00')
        self.assertContains(response, '</main>', count=1)
        self.assertContains(response, 'aria-expanded="false"')
        self.assertNotContains(response, 'Leitor conectado')

    def test_logout_ends_session(self):
        self.assertEqual(self.client.post('/usuarios/logout/').status_code, 302)
        self.assertEqual(self.client.get('/acervo/').status_code, 302)
