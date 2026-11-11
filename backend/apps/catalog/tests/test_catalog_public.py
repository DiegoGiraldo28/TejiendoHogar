"""Pruebas del catálogo y el detalle visibles al público."""
from decimal import Decimal
from time import perf_counter

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Producto
from conftest import crear_producto_prueba, imagen_png_prueba
from apps.inventory.models import Insumo
from apps.inventory.services import guardar_receta


def crear_producto_publico(indice, *, tipo=Producto.Tipo.DISPONIBLE, activo=True, stock=4):
    return crear_producto_prueba(
        nombre=f"Prenda {indice:03d}",
        descripcion="Prenda artesanal hecha a mano", precio=Decimal("45000"),
        imagen=imagen_png_prueba(f"prenda-{indice}.png"), tipo=tipo,
        tiempo_produccion_dias=5, stock_producto=stock, activo=activo,
    )


@pytest.mark.django_db
def test_catalogo_muestra_solo_activos_con_distintivos_y_paginacion(client):
    crear_producto_publico(1)
    crear_producto_publico(2, tipo=Producto.Tipo.SOBRE_PEDIDO)
    crear_producto_publico(3, stock=0)
    crear_producto_publico(4, activo=False)

    respuesta = client.get(reverse("catalog:lista"))

    assert respuesta.status_code == 200
    assert len(respuesta.context["pagina"].object_list) == 3
    assert b"Disponible" in respuesta.content
    assert b"Agotado" in respuesta.content
    assert b"se confecciona en 5 d\xc3\xadas" in respuesta.content
    assert b"Prenda 004" not in respuesta.content
    assert b'loading="lazy"' in respuesta.content


@pytest.mark.django_db
def test_catalogo_busca_filtra_por_tipo_y_muestra_estado_vacio(client):
    crear_producto_publico(1, tipo=Producto.Tipo.DISPONIBLE)
    crear_producto_publico(2, tipo=Producto.Tipo.SOBRE_PEDIDO)

    respuesta = client.get(reverse("catalog:lista"), {"q": "Prenda 002", "tipo": "Sobre_pedido"})
    assert len(respuesta.context["pagina"].object_list) == 1
    assert respuesta.context["pagina"].object_list[0].tipo == Producto.Tipo.SOBRE_PEDIDO

    vacio = client.get(reverse("catalog:lista"), {"q": "no existe"})
    assert b"No encontramos productos" in vacio.content


@pytest.mark.django_db
def test_catalogo_busca_sin_distinguir_tildes(client):
    crear_producto_prueba(nombre="Caf\u00e9 artesanal", tipo=Producto.Tipo.DISPONIBLE)

    respuesta = client.get(reverse("catalog:lista"), {"q": "cafe"})

    assert respuesta.status_code == 200
    assert "Caf\u00e9 artesanal".encode() in respuesta.content


@pytest.mark.django_db
def test_catalogo_pagina_en_lotes_de_doce(client):
    for indice in range(1, 15):
        crear_producto_publico(indice)
    primera = client.get(reverse("catalog:lista"))
    segunda = client.get(reverse("catalog:lista"), {"page": 2})
    assert len(primera.context["pagina"].object_list) == 12
    assert len(segunda.context["pagina"].object_list) == 2


@pytest.mark.django_db
def test_detalle_activo_muestra_descripcion_y_para_agotado_deshabilita_pedido(client):
    producto = crear_producto_publico(1, stock=0)
    respuesta = client.get(reverse("catalog:detalle", args=[producto.pk]))
    assert respuesta.status_code == 200
    assert b"Prenda artesanal hecha a mano" in respuesta.content
    assert b"disabled" in respuesta.content
    assert b"name=\"cantidad\"" not in respuesta.content


@pytest.mark.django_db
def test_detalle_sobre_pedido_sin_unidades_fabricables_mantiene_boton_deshabilitado(client, cliente):
    producto = crear_producto_publico(1, tipo=Producto.Tipo.SOBRE_PEDIDO)
    insumo = Insumo.objects.create(nombre="Tela agotada", unidad_medida=Insumo.Unidad.METROS)
    guardar_receta(producto=producto, lineas=[{"insumo": insumo, "cantidad_requerida": 1}])
    producto.activo = True
    producto.save(update_fields=["activo"])
    client.force_login(cliente)

    respuesta = client.get(reverse("catalog:detalle", args=[producto.pk]))

    assert b"Sin insumos por ahora" in respuesta.content
    assert b"disabled>Comprar ahora</button>" in respuesta.content


@pytest.mark.django_db
def test_producto_inactivo_desaparece_y_detalle_responde_404(client):
    producto = crear_producto_publico(1, activo=False)
    assert b"Prenda 001" not in client.get(reverse("catalog:lista")).content
    assert client.get(reverse("catalog:detalle", args=[producto.pk])).status_code == 404


@pytest.mark.django_db
def test_detalle_ofrece_pedido_a_cliente_y_vista_previa_a_emprendedora(client, cliente, emprendedora):
    producto = crear_producto_publico(1)
    insumo = Insumo.objects.create(
        nombre="Tela para pedido", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=1,
    )
    guardar_receta(producto=producto, lineas=[{"insumo": insumo, "cantidad_requerida": 1}])
    url = reverse("catalog:detalle", args=[producto.pk])
    anonimo = client.get(url)
    assert f"next=/catalogo/{producto.pk}/".encode() in anonimo.content
    client.force_login(cliente)
    assert b"Comprar ahora" in client.get(url).content
    client.force_login(emprendedora)
    previa = client.get(url)
    assert b"Vista previa para clientes" in previa.content
    assert b"Comprar ahora" not in previa.content


@pytest.mark.django_db
def test_login_desde_detalle_retorna_a_producto_si_next_es_seguro(client, cliente):
    producto = crear_producto_publico(1)
    destino = reverse("catalog:detalle", args=[producto.pk])
    respuesta = client.post(f"{reverse('accounts:login')}?next={destino}", {
        "correo": cliente.correo, "password": "ClaveFuerte-2026",
    })
    assert respuesta.status_code == 302
    assert respuesta.url == destino


@pytest.mark.django_db
def test_catalogo_tiene_consultas_constantes_y_responde_antes_de_dos_segundos(client):
    for indice in range(1, 101):
        crear_producto_publico(indice)

    inicio = perf_counter()
    with CaptureQueriesContext(connection) as consultas:
        respuesta = client.get(reverse("catalog:lista"))
    duracion = perf_counter() - inicio

    assert respuesta.status_code == 200
    assert len(consultas) <= 2
    assert duracion < 2


@pytest.mark.django_db
def test_precio_con_formato_unico_y_dias_solo_para_sobre_pedido(client):
    disponible = crear_producto_publico(1)
    encargo = crear_producto_publico(2, tipo=Producto.Tipo.SOBRE_PEDIDO)
    Producto.objects.filter(pk=encargo.pk).update(precio=Decimal("1289000"))

    lista = client.get(reverse("catalog:lista")).content.decode()
    assert "$45.000 COP" in lista and "$1.289.000 COP" in lista
    assert lista.count("se confecciona en") == 1

    detalle_disponible = client.get(reverse("catalog:detalle", args=[disponible.pk])).content.decode()
    assert "$45.000 COP" in detalle_disponible
    assert "Elaboración artesanal" not in detalle_disponible
    detalle_encargo = client.get(reverse("catalog:detalle", args=[encargo.pk])).content.decode()
    assert "Elaboración artesanal" in detalle_encargo


@pytest.mark.django_db
def test_nombre_con_script_se_muestra_escapado(client):
    crear_producto_prueba(
        nombre="<script>alert(1)</script>", descripcion="Prenda artesanal hecha a mano",
        precio=Decimal("45000"), imagen=imagen_png_prueba(), tipo=Producto.Tipo.DISPONIBLE,
        tiempo_produccion_dias=5, stock_producto=4,
    )
    contenido = client.get(reverse("catalog:lista")).content
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in contenido
    assert b"<script>alert(1)</script>" not in contenido
