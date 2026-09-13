"""Operações de estoque compartilhadas por HTML, API e Admin."""
from decimal import Decimal
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from usuarios.permissions import permitido
from .models import Exemplar, Produto

COPY_FIELDS = ('produto', 'codigo_interno', 'estado_conservacao', 'preco', 'localizacao', 'status')
TRANSITIONS = {
    'disponivel': {'reservado', 'vendido', 'cancelado'},
    'reservado': {'disponivel', 'vendido', 'cancelado'},
    'vendido': {'disponivel'},
    'cancelado': {'disponivel'},
}


def snapshot(item):
    result = {f: str(getattr(item, f)) if isinstance(getattr(item, f), Decimal) else getattr(item, f)
              for f in COPY_FIELDS if f != 'produto'}
    result.update(produto_id=item.produto_id, titulo=item.produto.titulo)
    return result


def validate_transition(old, new, user=None):
    if old == new:
        return
    if new not in TRANSITIONS.get(old, set()):
        raise ValidationError({'status': 'Transição de estoque inválida.'})
    if user is not None and (old in {'vendido', 'cancelado'} or new == 'cancelado') and not permitido(user, 'excluir_acervo'):
        raise PermissionDenied('Somente administradores podem cancelar ou reativar este registro.')


def event(item, user, kind, before, after, details=''):
    from movimentacoes.models import Movimentacao
    return Movimentacao.objects.create(item=item, usuario=user, tipo=kind,
        anterior=before, novo=after, detalhes=details)


@transaction.atomic
def salvar_exemplar(*, usuario, dados, exemplar=None):
    if not permitido(usuario, 'editar_acervo'):
        raise PermissionDenied('Perfil sem autorização para alterar o acervo.')
    before = {}
    if exemplar is not None and exemplar.pk:
        item = Exemplar.objects.select_for_update().select_related('produto').get(pk=exemplar.pk)
        before = snapshot(item)
        # Evita sobrescrita silenciosa de formulário/API com objeto desatualizado.
        if exemplar.data_atualizacao != item.data_atualizacao:
            raise ValidationError('O exemplar foi alterado por outro usuário. Recarregue a página.')
    else:
        item = Exemplar(usuario_responsavel=usuario)
    for key, value in dados.items():
        if key not in COPY_FIELDS:
            raise ValidationError('Campo de estoque não permitido.')
        setattr(item, key, value)
    if before:
        validate_transition(before['status'], item.status, usuario)
    elif item.status != 'disponivel':
        raise ValidationError({'status': 'Novos exemplares entram como disponíveis.'})
    item.full_clean()
    item.save()
    after = snapshot(item)
    if not before:
        event(item, usuario, 'entrada', {}, after)
    elif before != after:
        kind = 'edicao'
        if before['status'] != after['status']:
            kind = {'reservado': 'reserva', 'vendido': 'venda', 'cancelado': 'cancelamento'}.get(after['status'], 'alteracao_status')
            if after['status'] == 'disponivel':
                kind = 'cancelamento_reserva' if before['status'] == 'reservado' else 'cancelamento'
        event(item, usuario, kind, before, after)
        for field, kind in [('preco', 'alteracao_preco'), ('localizacao', 'mudanca_localizacao')]:
            if before[field] != after[field]:
                event(item, usuario, kind, before, after)
    return item


def excluir_exemplar(item, usuario):
    if not permitido(usuario, 'excluir_acervo'):
        raise PermissionDenied('Exclusão restrita a administradores.')
    if item.status == 'vendido':
        raise ValidationError('Cancele a venda antes de retirar o exemplar do estoque.')
    return salvar_exemplar(usuario=usuario, exemplar=item, dados={'status': 'cancelado'})


@transaction.atomic
def salvar_produto(produto, usuario):
    if not permitido(usuario, 'editar_acervo'):
        raise PermissionDenied
    if produto.pk:
        old = Produto.objects.select_for_update().get(pk=produto.pk)
        before = {f: getattr(old, f) for f in ('titulo', 'tipo', 'ean', 'ano', 'artista_diretor', 'descricao', 'gravadora_distribuidora', 'origem', 'identificadores', 'metadados')}
        before['categoria_id'] = old.categoria_id
    else:
        before = {}
    produto.full_clean()
    produto.save()
    if before:
        after = {key: getattr(produto, key) for key in before}
        if before != after:
            for item in produto.exemplares.all().iterator():
                event(item, usuario, 'edicao', {'produto': before}, {'produto': after}, 'Metadados do produto atualizados.')
    return produto
