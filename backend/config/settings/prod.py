"""Ajustes de producción. AWS queda preparado como referencia, sin activarse."""
import os
from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = [host.strip() for host in os.environ["ALLOWED_HOSTS"].split(",") if host.strip()]
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "root": {"handlers": ["console"], "level": "INFO"}}
# TODO: configurar django-storages/boto3 y S3 cuando se habilite el bucket.
# TODO: configurar SES y credenciales desde el entorno de despliegue.
# TODO: preparar RDS PostgreSQL y Elastic Beanstalk sin guardar secretos aquí.
