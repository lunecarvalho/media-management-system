from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from acervo.models import Categoria, Item
from movimentacoes.models import Movimentacao

from .serializers import CategoriaSerializer, ItemSerializer, MovimentacaoSerializer


class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all().order_by('nome')
    serializer_class = CategoriaSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.select_related('categoria').all()
    serializer_class = ItemSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(usuario_responsavel=self.request.user)

    @action(detail=False, methods=['get'], url_path='codigo/(?P<codigo>[^/.]+)')
    def por_codigo(self, request, codigo=None):
        item = self.get_queryset().filter(codigo_barras=codigo).first()
        if item is None:
            return Response({'detail': 'Item não encontrado.'}, status=404)
        return Response(self.get_serializer(item).data)


class MovimentacaoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Movimentacao.objects.select_related('item', 'usuario').all()
    serializer_class = MovimentacaoSerializer
    permission_classes = [permissions.IsAuthenticated]
