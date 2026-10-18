"""Configuración de las páginas legales informativas."""
from django.apps import AppConfig


class LegalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.legal"
    label = "legal"
