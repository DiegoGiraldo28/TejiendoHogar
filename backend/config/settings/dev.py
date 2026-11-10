"""Ajustes locales de desarrollo."""
import os

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.getenv("SECRET_KEY", "clave-insegura-solo-para-desarrollo")
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
