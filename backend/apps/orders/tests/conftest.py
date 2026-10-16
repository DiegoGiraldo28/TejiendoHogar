"""Aísla las imágenes de los productos en los casos de prueba."""
import pytest


@pytest.fixture(autouse=True)
def media_temporal(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
