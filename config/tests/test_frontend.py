from django.test import TestCase
from django.contrib.auth.models import User
from usuarios.models import Perfil
from acervo.models import Produto, Exemplar, Categoria
from html.parser import HTMLParser
from django.urls import reverse


class ActiveMenuParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active_links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'a' and 'menu-item' in classes and 'ativo' in classes:
            self.active_links.append(attrs['href'])


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

    def test_registration_and_catalog_have_exclusive_active_menu(self):
        for route in ('acervo:cadastrar', 'acervo:lista', 'codigo_barras'):
            with self.subTest(route=route):
                url = reverse(route)
                response = self.client.get(url)
                parser = ActiveMenuParser()
                parser.feed(response.content.decode())
                self.assertEqual(parser.active_links, [url])

    def test_registration_keeps_page_heading_without_card_heading(self):
        response = self.client.get(reverse('acervo:cadastrar'))
        self.assertContains(response, '<h1>Cadastrar item</h1>', html=True)
        self.assertContains(response, 'Adicione um novo CD ou DVD ao acervo.')
        self.assertNotContains(response, '<h2>Cadastrar item</h2>')
        self.assertNotContains(response, 'Preencha os dados para incluir o item no acervo.')
        self.assertNotContains(response, 'class="formulario-cabecalho')
        self.assertContains(response, '<h3 id="titulo-produto">Produto</h3>', html=True)
        self.assertContains(response, '<h3 id="titulo-exemplar">Exemplar</h3>', html=True)
