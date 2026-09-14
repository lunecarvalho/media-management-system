from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from usuarios.models import Perfil
from acervo.models import Exemplar, Produto, Categoria
from movimentacoes.models import Movimentacao
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from django.test import RequestFactory
from django.urls import reverse
from config.views import dashboard

class DashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dashboard')
        Perfil.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.product = Produto.objects.create(titulo='Album', tipo='CD', artista_diretor='Band', categoria=Categoria.objects.create(nome='Rock'))

    def test_indicators_and_excluded_sales(self):
        for n, status in enumerate(['disponivel', 'reservado', 'vendido', 'cancelado']):
            Exemplar.objects.create(produto=self.product, codigo_interno=str(n), preco=10, status=status, usuario_responsavel=self.user)
        response = self.client.get('/')
        self.assertEqual(response.context['valor_estoque'], Decimal('20'))
        self.assertEqual(response.context['metricas']['cds'], 2)
        self.assertEqual(response.context['metricas']['dvds'], 0)
        self.assertEqual(response.context['metricas']['disponiveis'], 1)
        self.assertEqual(response.context['vendidos_mes'], 0)
        self.assertNotContains(response, '1.842')

    def test_pagination_and_search(self):
        Exemplar.objects.bulk_create([Exemplar(produto=self.product, codigo_interno=str(n), usuario_responsavel=self.user) for n in range(23)])
        page = self.client.get('/acervo/?q=Album&page=2')
        self.assertEqual(len(page.context['itens']), 3)
        self.assertContains(page, 'q=Album')
        self.assertEqual(self.client.get('/acervo/?page=bad').status_code, 200)

    def copy(self, product=None, status='disponivel', price=None):
        return Exemplar.objects.create(produto=product or self.product, codigo_interno=f'T{Exemplar.objects.count()}',
            status=status, preco=price, usuario_responsavel=self.user)

    def sale(self, date, kind='venda', item=None):
        event = Movimentacao.objects.create(item=item or self.copy(), tipo=kind, usuario=self.user)
        Movimentacao.objects.filter(pk=event.pk).update(data=date)
        return event

    def test_cd_dvd_are_physical_stock_and_value_excludes_sold_cancelled(self):
        dvd = Produto.objects.create(tipo='DVD', titulo='Filme', artista_diretor='Diretor', categoria=self.product.categoria)
        self.copy(price=Decimal('12.50'))
        self.copy(status='reservado', price=Decimal('7.50'))
        self.copy(product=dvd, price=0)
        self.copy(product=dvd, price=None)
        self.copy(product=dvd, status='vendido', price=900)
        self.copy(status='cancelado', price=800)
        response = self.client.get('/')
        self.assertEqual(response.context['metricas']['cds'], 2)
        self.assertEqual(response.context['metricas']['dvds'], 2)
        self.assertEqual(response.context['metricas']['disponiveis'], 3)
        self.assertEqual(response.context['valor_estoque'], Decimal('20.00'))

    def test_sales_local_month_boundary_and_seven_days(self):
        now = datetime(2026, 9, 2, 15, tzinfo=dt_timezone.utc)
        self.sale(datetime(2026, 9, 1, 1, tzinfo=dt_timezone.utc))  # 31/08 em São Paulo
        self.sale(datetime(2026, 9, 1, 3, tzinfo=dt_timezone.utc))  # 01/09 local
        self.sale(now)
        self.sale(now - timedelta(days=6))
        self.sale(now - timedelta(days=7))  # fora da janela
        self.sale(now + timedelta(days=1))  # futuro não conta
        self.sale(now, kind='entrada')
        self.sale(now, kind='cancelamento')
        with patch('config.views.timezone.now', return_value=now):
            response = self.client.get('/')
        self.assertEqual(response.context['vendidos_mes'], 2)
        self.assertEqual(response.context['vendas_total'], 4)
        days = response.context['vendas_dias']
        self.assertEqual(len(days), 7)
        self.assertEqual(str(days[0]['data']), '2026-08-27')
        self.assertEqual(str(days[-1]['data']), '2026-09-02')
        self.assertEqual([day['total'] for day in days], [1, 0, 0, 0, 1, 1, 1])

    def test_month_sales_include_earlier_days_and_cancellation_does_not_erase_event(self):
        now = datetime(2026, 9, 20, 15, tzinfo=dt_timezone.utc)
        item = self.copy(status='disponivel')
        self.sale(now - timedelta(days=15), item=item)
        self.sale(now - timedelta(days=1), item=item)
        self.sale(now, kind='cancelamento', item=item)
        with patch('config.views.timezone.now', return_value=now):
            response = self.client.get('/')
        self.assertEqual(response.context['vendidos_mes'], 2)
        self.assertEqual(response.context['vendas_total'], 1)
        self.assertContains(response, 'cancelamentos não descontados')

    def test_top_categories_count_copies_and_limit_to_four(self):
        for index in range(5):
            category = Categoria.objects.create(nome=f'Categoria {index}')
            product = Produto.objects.create(tipo='CD', titulo=str(index), artista_diretor='A', categoria=category)
            for _ in range(index + 1):
                self.copy(product=product)
            self.copy(product=product, status='vendido')
        rows = self.client.get('/').context['top_categorias']
        self.assertEqual([row['total'] for row in rows], [5, 4, 3, 2])
        self.assertEqual(rows[0]['produto__categoria__nome'], 'Categoria 4')

    def test_empty_dashboard_and_real_links(self):
        self.product.delete()
        Categoria.objects.all().delete()
        response = self.client.get('/')
        for key in ('cds', 'dvds', 'disponiveis'):
            self.assertEqual(response.context['metricas'][key], 0)
        self.assertEqual(response.context['valor_estoque'], 0)
        self.assertEqual(response.context['vendidos_mes'], 0)
        self.assertEqual(response.context['vendas_total'], 0)
        self.assertEqual(response.context['top_categorias'], [])
        self.assertTrue(all(day['altura'] == 0 for day in response.context['vendas_dias']))
        self.assertContains(response, 'R$ 0,00')
        self.assertContains(response, 'Nenhuma movimentação registrada.')
        self.assertContains(response, 'Nenhuma categoria com exemplares')
        for route in ('acervo:cadastrar', 'codigo_barras', 'acervo:lista', 'movimentacoes:lista'):
            self.assertContains(response, f'href="{reverse(route)}"')
        for fictitious in ('1.842', '2.411', '47k', '+12 este mês', '88%'):
            self.assertNotContains(response, fictitious)

    def test_latest_movements_are_ordered_limited_and_show_current_status(self):
        now = datetime(2026, 9, 20, 15, tzinfo=dt_timezone.utc)
        item = self.copy(status='reservado')
        events = [self.sale(now - timedelta(hours=i), kind='entrada', item=item) for i in range(12)]
        response = self.client.get('/')
        self.assertEqual([event.pk for event in response.context['recentes']], [event.pk for event in events[:10]])
        self.assertContains(response, 'Status atual')
        self.assertContains(response, 'Reservado')

    def test_dashboard_aggregations_have_bounded_query_count(self):
        for _ in range(12):
            self.sale(datetime(2026, 9, 1, tzinfo=dt_timezone.utc))
        request = RequestFactory().get('/')
        def evaluate(_request, _template, context):
            for event in context['recentes']:
                str(event.item.produto.titulo)
                str(event.usuario.username)
            return context
        with patch('config.views.render', side_effect=evaluate), self.assertNumQueries(4):
            dashboard(request)

    def test_dashboard_requires_active_permission(self):
        Perfil.objects.filter(usuario=self.user).update(ativo=False)
        self.assertEqual(self.client.get('/').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/').status_code, 302)
