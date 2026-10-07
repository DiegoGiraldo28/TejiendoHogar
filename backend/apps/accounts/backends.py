"""Autenticación por correo sin alterar el nombre de usuario del modelo."""
from django.contrib.auth.backends import ModelBackend
from .models import Usuario


class CorreoBackend(ModelBackend):
    """Busca las cuentas ignorando mayúsculas en el correo."""

    def authenticate(self, request, username=None, password=None, correo=None, **kwargs):
        direccion = (correo or username or "").strip().lower()
        try:
            usuario = Usuario.objects.get(correo__iexact=direccion)
        except Usuario.DoesNotExist:
            Usuario().set_password(password)
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
