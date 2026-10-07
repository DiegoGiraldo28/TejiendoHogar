"""Configuración de la aplicación de usuarios."""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"

    def ready(self):
        """Desconecta el guardado de last_login, columna ausente del esquema."""
        from django.contrib.auth.models import update_last_login
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.disconnect(update_last_login)
