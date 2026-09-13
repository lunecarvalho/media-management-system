"""Política única para HTML, API e administração."""
from rest_framework.permissions import BasePermission, SAFE_METHODS

ROLES = {
    'funcionario': {'consultar', 'editar_acervo'},
    'administrador': {'consultar', 'editar_acervo', 'excluir_acervo', 'categorias'},
    'proprietario': {'consultar', 'editar_acervo', 'excluir_acervo', 'categorias', 'usuarios'},
}


def permitido(user, action='consultar'):
    if not user.is_authenticated or not user.is_active:
        return False
    perfil = getattr(user, 'perfil', None)
    if perfil is not None and not perfil.ativo:
        return False
    if user.is_superuser:
        return True
    return perfil is not None and action in ROLES.get(perfil.tipo, set())


class AcessoAPI(BasePermission):
    def has_permission(self, request, view):
        action = 'consultar'
        if request.method not in SAFE_METHODS:
            action = getattr(view, 'write_permission', 'editar_acervo')
            if request.method == 'DELETE' and action == 'editar_acervo':
                action = 'excluir_acervo'
        return permitido(request.user, action)
