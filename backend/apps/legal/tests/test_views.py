"""Pruebas de las páginas legales estáticas."""
import pytest
from django.urls import reverse


@pytest.mark.parametrize("ruta,texto", [
    ("legal:terminos", "Términos y condiciones"),
    ("legal:privacidad", "Ley 1581 de 2012"),
    ("legal:cookies", "Política de cookies"),
])
def test_pagina_legal_publica_y_renderiza_contenido(client, ruta, texto):
    respuesta = client.get(reverse(ruta))

    assert respuesta.status_code == 200
    assert texto.encode() in respuesta.content


def test_politica_privacidad_identifica_placeholders_de_responsable(client):
    respuesta = client.get(reverse("legal:privacidad"))

    assert b"[Nombre legal del responsable]" in respuesta.content
    assert b"[NIT]" in respuesta.content
    assert b"[Correo de contacto]" in respuesta.content
