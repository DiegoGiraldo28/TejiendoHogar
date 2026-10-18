"""Ajustes de producción en AWS (Elastic Beanstalk, RDS, S3 y SES)."""
import os
from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = [host.strip() for host in os.environ["ALLOWED_HOSTS"].split(",") if host.strip()]
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
LOGGING = {"version": 1, "disable_existing_loggers": False, "handlers": {"console": {"class": "logging.StreamHandler"}}, "root": {"handlers": ["console"], "level": "INFO"}}

# --- Archivos subidos (imágenes de productos) en S3 ---
# Las credenciales las aporta el rol de IAM de la instancia; no se guardan aquí.
STORAGES = {
    "default": {"BACKEND": "storages.backends.s3.S3Storage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
AWS_QUERYSTRING_AUTH = True  # URLs firmadas: el bucket sigue siendo privado

# --- Correo con Amazon SES (SMTP) ---
EMAIL_HOST = os.environ.get("EMAIL_HOST", "email-smtp.us-east-1.amazonaws.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

# TODO: activar SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE y CSRF_COOKIE_SECURE cuando haya HTTPS.