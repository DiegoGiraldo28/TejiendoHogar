"""Contador de la bolsa para la navegación de la Cliente, leído de la sesión sin consultas."""
from apps.accounts.models import Usuario
from .carrito import Bolsa


def bolsa(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated or usuario.rol != Usuario.Rol.CLIENTE:
        return {}
    return {"unidades_bolsa": Bolsa(request.session).total_unidades}
