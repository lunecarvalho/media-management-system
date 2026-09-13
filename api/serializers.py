from rest_framework import serializers
from acervo.models import Exemplar, Produto, Categoria
from movimentacoes.models import Movimentacao

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'descricao']

class ProdutoSerializer(serializers.ModelSerializer):
    def validate_ean(self, value):
        return value.strip() if value else None
    class Meta:
        model = Produto
        fields = ['id', 'tipo', 'titulo', 'artista_diretor', 'ean', 'categoria', 'ano',
                  'gravadora_distribuidora', 'descricao', 'identificadores', 'metadados', 'origem']
        read_only_fields = ['identificadores', 'metadados', 'origem']

class ItemSerializer(serializers.ModelSerializer):
    titulo = serializers.ReadOnlyField()
    tipo = serializers.ReadOnlyField()
    artista_diretor = serializers.ReadOnlyField()
    codigo_barras = serializers.ReadOnlyField()
    categoria_nome = serializers.CharField(source='produto.categoria.nome', read_only=True)
    produto_detalhe = ProdutoSerializer(source='produto', read_only=True)

    class Meta:
        model = Exemplar
        fields = ['id', 'produto', 'produto_detalhe', 'codigo_interno', 'codigo_barras', 'titulo',
                  'tipo', 'artista_diretor', 'categoria_nome', 'estado_conservacao', 'preco', 'localizacao',
                  'status', 'data_cadastro', 'data_atualizacao']
        read_only_fields = ['data_cadastro', 'data_atualizacao']

class MovimentacaoSerializer(serializers.ModelSerializer):
    item_titulo = serializers.CharField(source='item.titulo', read_only=True)
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)
    class Meta:
        model = Movimentacao
        fields = ['id', 'item', 'item_titulo', 'tipo', 'usuario', 'usuario_nome', 'data', 'detalhes', 'anterior', 'novo']
        read_only_fields = fields
