"""Pruebas aisladas de los ajustes específicos de producción."""
import importlib.util
from pathlib import Path

import pytest


@pytest.mark.parametrize("activo", ["true", "1", "yes", "false"])
def test_ajustes_https_segun_variable(monkeypatch, activo):
    monkeypatch.setenv("SECRET_KEY", "x" * 64)
    monkeypatch.setenv("ALLOWED_HOSTS", "ejemplo.com")
    monkeypatch.setenv("AWS_STORAGE_BUCKET_NAME", "bucket-prueba")
    monkeypatch.setenv("HTTPS_ACTIVO", activo)
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "https://ejemplo.com, https://www.ejemplo.com ")

    ruta = Path(__file__).resolve().parents[3] / "config" / "settings" / "prod.py"
    spec = importlib.util.spec_from_file_location("config.settings.prod_prueba", ruta)
    ajustes = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ajustes)

    assert ajustes.CSRF_TRUSTED_ORIGINS == ["https://ejemplo.com", "https://www.ejemplo.com"]
    assert ajustes.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert ajustes.SECURE_REFERRER_POLICY == "same-origin"
    assert ajustes.HTTPS_ACTIVO is (activo.lower() in {"true", "1", "yes"})
    if ajustes.HTTPS_ACTIVO:
        assert ajustes.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        assert ajustes.SECURE_SSL_REDIRECT is True
        assert ajustes.SESSION_COOKIE_SECURE is True
        assert ajustes.CSRF_COOKIE_SECURE is True
        assert ajustes.SECURE_HSTS_SECONDS == 3600
        assert ajustes.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert not hasattr(ajustes, "SECURE_HSTS_PRELOAD")
    else:
        assert not hasattr(ajustes, "SECURE_PROXY_SSL_HEADER")
        assert not hasattr(ajustes, "SECURE_SSL_REDIRECT")
        assert not hasattr(ajustes, "SESSION_COOKIE_SECURE")
        assert not hasattr(ajustes, "CSRF_COOKIE_SECURE")
        assert not hasattr(ajustes, "SECURE_HSTS_SECONDS")
        assert not hasattr(ajustes, "SECURE_HSTS_INCLUDE_SUBDOMAINS")
