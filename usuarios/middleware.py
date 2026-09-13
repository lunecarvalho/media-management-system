from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin
from .permissions import permitido


class AcessoInternoMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if match.namespace == 'api':
            return None
        if match.view_name in {'usuarios:login', 'usuarios:logout', 'health', 'readiness', 'admin:login', 'admin:logout'}:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        action = 'consultar'
        if match.namespace in {'admin', 'usuarios'}:
            action = 'usuarios'
        elif match.namespace == 'categorias' and (request.method == 'POST' or match.url_name != 'lista'):
            action = 'categorias'
        elif match.namespace == 'acervo':
            if match.url_name == 'excluir':
                action = 'excluir_acervo'
            elif match.url_name not in {'lista', 'detalhe'}:
                action = 'editar_acervo'
        if not permitido(request.user, action):
            raise PermissionDenied('Seu perfil não permite esta operação.')
