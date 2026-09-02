from rest_framework import serializers
from acervo.models import Item, Categoria
from movimentacoes.models import Movimentacao


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nome', 'descricao']


class ItemSerializer(serializers.ModelSerializer):
    categoria_nome = serializers.CharField(source='categoria.nome', read_only=True)

    class Meta:
        model = Item
        fields = [
            'id', 'tipo', 'titulo', 'artista_diretor', 'codigo_barras',
            'categoria', 'categoria_nome', 'ano', 'gravadora_distribuidora',
            'descricao', 'estado_conservacao', 'preco', 'localizacao',
            'status', 'data_cadastro', 'data_atualizacao',
        ]
        read_only_fields = ['data_cadastro', 'data_atualizacao']


class MovimentacaoSerializer(serializers.ModelSerializer):
    item_titulo = serializers.CharField(source='item.titulo', read_only=True)
    usuario_nome = serializers.CharField(source='usuario.username', read_only=True)

    class Meta:
        model = Movimentacao
        fields = ['id', 'item', 'item_titulo', 'tipo', 'usuario', 'usuario_nome', 'data', 'detalhes']
        read_only_fields = ['data']
