from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from acervo.models import Categoria, Item, Produto
from movimentacoes.models import Movimentacao

from .serializers import CategoriaSerializer, ItemSerializer, MovimentacaoSerializer, ProdutoSerializer
from usuarios.permissions import AcessoAPI
from acervo.services import salvar_exemplar, excluir_exemplar, salvar_produto


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('nome')
    serializer_class = CategoriaSerializer
    permission_classes = [AcessoAPI]
    write_permission = 'categorias'


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related('produto__categoria').all()
    serializer_class = ItemSerializer
    permission_classes = [AcessoAPI]

    def perform_create(self, serializer):
        serializer.instance = salvar_exemplar(usuario=self.request.user, dados=serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = salvar_exemplar(usuario=self.request.user, dados=serializer.validated_data, exemplar=serializer.instance)

    def perform_destroy(self, instance):
        excluir_exemplar(instance, self.request.user)

    @action(detail=False, methods=['get'], url_path='codigo/(?P<codigo>[^/.]+)')
    def por_codigo(self, request, codigo=None):
        from acervo.barcodes import localizar
        item, produto = localizar(codigo, request.query_params.get('modo', 'auto'))
        if item:
            return Response(self.get_serializer(item).data)
        if produto:
            page = self.paginate_queryset(produto.exemplares.select_related('produto__categoria').all())
            response = self.get_paginated_response(self.get_serializer(page, many=True).data)
            response.data.update(tipo_codigo='ean', produto=ProdutoSerializer(produto).data)
            return response
        from acervo.barcode_flow import consultar_metadados, cadastro_manual_url, codigo_comercial, validar_consulta
        from django.core.exceptions import ValidationError
        from usuarios.permissions import permitido
        codigo = codigo.strip()
        modo = request.query_params.get('modo', 'auto')
        try:
            validar_consulta(codigo, modo)
        except ValidationError:
            return Response({'erro': {'codigo': 'invalido', 'detalhes': 'Informe um código de até 40 caracteres, sem espaços, e um modo válido.'}}, status=400)
        if request.query_params.get('metadados') == '1':
            if not permitido(request.user, 'editar_acervo'):
                return Response({'detail': 'Sem permissão para consultar metadados.'}, status=403)
            data, status = consultar_metadados(codigo, modo, request.user)
            return Response(data, status=status)
        return Response({'erro': {'codigo': 'nao_encontrado', 'detalhes': 'Código não encontrado no acervo local.'},
            'metadados_disponiveis': codigo_comercial(codigo, modo) and permitido(request.user, 'editar_acervo'),
            'cadastro_url': cadastro_manual_url(codigo, modo)}, status=404)



class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.select_related('categoria').all()
    serializer_class = ProdutoSerializer
    permission_classes = [AcessoAPI]

    def perform_create(self, serializer):
        serializer.instance = salvar_produto(Produto(**serializer.validated_data), self.request.user)

    def perform_update(self, serializer):
        for field, value in serializer.validated_data.items():
            setattr(serializer.instance, field, value)
        serializer.instance = salvar_produto(serializer.instance, self.request.user)


class MovimentacaoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Movimentacao.objects.select_related('item', 'usuario').all()
    serializer_class = MovimentacaoSerializer
    permission_classes = [AcessoAPI]
