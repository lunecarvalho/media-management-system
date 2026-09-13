import os
import subprocess
import sys
from pathlib import Path
from django.test import SimpleTestCase


class MigrationTests(SimpleTestCase):
    def test_legacy_migration_preserves_ids_metadata_and_history(self):
        script = """
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
executor = MigrationExecutor(connection)
targets = [('acervo','0001_initial'),('movimentacoes','0001_initial'),('usuarios','0002_alter_perfil_tipo')]
executor.migrate(targets)
apps = executor.loader.project_state(targets).apps
user = apps.get_model('auth','User').objects.create(username='legacy')
category = apps.get_model('acervo','Categoria').objects.create(nome='Rock')
item = apps.get_model('acervo','Item').objects.create(id=37,tipo='CD',titulo='Legacy',
    artista_diretor='Artist',codigo_barras='00987',categoria=category,ano=2001,
    gravadora_distribuidora='Label',descricao='Original',preco='12.50',usuario_responsavel=user)
event = apps.get_model('movimentacoes','Movimentacao').objects.create(item=item,tipo='cadastro',usuario=user,detalhes='Preserve')
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from acervo.models import Exemplar
from movimentacoes.models import Movimentacao
copy = Exemplar.objects.get(pk=37)
assert copy.produto.titulo == 'Legacy'
assert copy.produto.ean == '00987'
assert copy.produto.ano == 2001
assert copy.produto.descricao == 'Original'
assert copy.codigo_interno == '00987'
assert str(copy.preco) == '12.50'
assert copy.usuario_responsavel_id == user.pk
assert Movimentacao.objects.get(pk=event.pk).item_id == 37
assert Movimentacao.objects.get(pk=event.pk).detalhes == 'Preserve'
"""
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.test_settings', TEST_DATABASE_URL='')
        result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
