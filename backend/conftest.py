"""Fixtures compartidas entre las apps del proyecto."""
import pytest
from django.contrib.auth import get_user_model

Usuario = get_user_model()


@pytest.fixture
def cliente(db):
    return Usuario.objects.create_user("ana@example.com", "ClaveFuerte-2026", nombre="Ana")


@pytest.fixture
def emprendedora(db):
    return Usuario.objects.create_superuser("taller@example.com", "ClaveFuerte-2026", nombre="Taller")
