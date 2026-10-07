"""Control de acceso sencillo basado en los roles del usuario."""
from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import AccessMixin


def rol_requerido(*roles):
    """Permite la vista a usuarios autenticados que tengan uno de los roles."""
    def decorador(vista):
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.rol not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)
        return protegida
    return decorador


class RolRequeridoMixin(AccessMixin):
    """Mixin equivalente para vistas basadas en clases."""
    roles_permitidos = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.rol not in self.roles_permitidos:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
