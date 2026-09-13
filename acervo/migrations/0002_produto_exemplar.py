from django.db import migrations, models
import django.db.models.deletion


def copiar_produtos(apps, schema_editor):
    Exemplar = apps.get_model('acervo', 'Exemplar')
    Produto = apps.get_model('acervo', 'Produto')
    alias = schema_editor.connection.alias
    campos = ('tipo', 'titulo', 'artista_diretor', 'categoria_id', 'ano', 'gravadora_distribuidora', 'descricao')
    for item in Exemplar.objects.using(alias).all().iterator(chunk_size=500):
        produto = Produto.objects.using(alias).create(ean=item.codigo_interno, **{c: getattr(item, c) for c in campos})
        Exemplar.objects.using(alias).filter(pk=item.pk).update(produto_id=produto.pk)


class Migration(migrations.Migration):
    dependencies = [('acervo', '0001_initial'), ('movimentacoes', '0001_initial')]
    operations = [
        migrations.RenameModel('Item', 'Exemplar'),
        migrations.RenameField('exemplar', 'codigo_barras', 'codigo_interno'),
        migrations.CreateModel(name='Produto', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
            ('tipo', models.CharField(max_length=10, choices=[('CD', 'CD'), ('DVD', 'DVD')])),
            ('titulo', models.CharField(max_length=200)),
            ('artista_diretor', models.CharField(max_length=200)),
            ('ean', models.CharField(max_length=20, unique=True, null=True, blank=True)),
            ('ano', models.IntegerField(null=True, blank=True)),
            ('gravadora_distribuidora', models.CharField(max_length=200, blank=True)),
            ('descricao', models.TextField(blank=True)),
            ('identificadores', models.JSONField(default=dict, blank=True)),
            ('metadados', models.JSONField(default=dict, blank=True)),
            ('origem', models.CharField(max_length=100, blank=True)),
            ('categoria', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='acervo.categoria')),
        ], options={'ordering': ['titulo', 'pk']}),
        migrations.AddField('exemplar', 'produto', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='exemplares', to='acervo.produto')),
        # Irreversível intencionalmente: retornar ao model antigo perderia produtos compartilhados.
        migrations.RunPython(copiar_produtos),
        migrations.AlterField('exemplar', 'produto', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='exemplares', to='acervo.produto')),
        *[migrations.RemoveField('exemplar', campo) for campo in ('tipo', 'titulo', 'artista_diretor', 'categoria', 'ano', 'gravadora_distribuidora', 'descricao')],
        migrations.AlterField('exemplar', 'codigo_interno', models.CharField(max_length=40, unique=True)),
        migrations.AlterField('exemplar', 'status', models.CharField(max_length=20, default='disponivel', choices=[('disponivel', 'Disponível'), ('reservado', 'Reservado'), ('vendido', 'Vendido'), ('cancelado', 'Cancelado')])),
        migrations.AlterModelOptions('exemplar', {'ordering': ['-data_cadastro', '-pk'], 'verbose_name_plural': 'Exemplares'}),
        migrations.AlterModelOptions('categoria', {'ordering': ['nome', 'pk'], 'verbose_name_plural': 'Categorias'}),
    ]
