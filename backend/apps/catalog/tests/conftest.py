"""Aísla las imágenes de prueba en el directorio temporal de cada caso."""
import pytest


@pytest.fixture(autouse=True)
def media_temporal(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
