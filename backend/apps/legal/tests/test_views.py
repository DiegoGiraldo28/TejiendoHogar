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


@pytest.mark.parametrize("ruta", ["legal:terminos", "legal:privacidad", "legal:cookies"])
def test_paginas_legales_muestran_datos_del_responsable(client, ruta):
    respuesta = client.get(reverse(ruta))

    assert b"Equipo TejiendoHogar" in respuesta.content
    assert b"900.123.456-7 (ficticio, con fines acad\xc3\xa9micos)" in respuesta.content
    assert b"diegoh.giraldoc@uqvirtual.edu.co" in respuesta.content
