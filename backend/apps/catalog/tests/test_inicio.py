from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Producto
from apps.catalog.services import crear_producto, productos_destacados
from .test_catalog_public import crear_producto_publico
from .test_catalog import imagen


@pytest.mark.django_db
def test_inicio_anonimo_muestra_bienvenida_y_enlaces(client):
    respuesta = client.get(reverse("inicio"))

    assert respuesta.status_code == 200
    assert any(template.name == "inicio.html" for template in respuesta.templates)
    assert reverse("catalog:lista").encode() in respuesta.content
    assert reverse("accounts:registro").encode() in respuesta.content
    assert reverse("accounts:login").encode() in respuesta.content


@pytest.mark.django_db
def test_inicio_muestra_hasta_cuatro_productos_activos_mas_recientes(client):
    productos = []
    for indice in range(1, 7):
        producto = crear_producto_publico(indice)
        producto.fecha_creacion = timezone.now() + timedelta(seconds=indice)
        producto.save(update_fields=["fecha_creacion"])
        productos.append(producto)
    inactivo = crear_producto_publico(7, activo=False)
    inactivo.fecha_creacion = timezone.now() + timedelta(seconds=20)
    inactivo.save(update_fields=["fecha_creacion"])

    respuesta = client.get(reverse("inicio"))
    destacados_esperados = sorted(productos, key=lambda producto: producto.fecha_creacion, reverse=True)[:4]

    assert len(respuesta.context["destacados"]) == 4
    assert [producto.pk for producto in respuesta.context["destacados"]] == [
        producto.pk for producto in destacados_esperados
    ]
    for producto in destacados_esperados:
        assert producto.nombre.encode() in respuesta.content
    assert inactivo.nombre.encode() not in respuesta.content
    assert productos[0].nombre.encode() not in respuesta.content
    assert b'loading="lazy"' in respuesta.content


@pytest.mark.django_db
def test_inicio_no_renderiza_seccion_de_destacados_sin_productos_activos(client):
    crear_producto_publico(1, activo=False)

    respuesta = client.get(reverse("inicio"))

    assert b"Reci\xc3\xa9n salidas del taller" not in respuesta.content


@pytest.mark.django_db
def test_inicio_redirige_a_usuarios_segun_su_rol(client, cliente, emprendedora):
    client.force_login(cliente)
    respuesta_cliente = client.get(reverse("inicio"))
    assert respuesta_cliente.status_code == 302
    assert respuesta_cliente.url == reverse("catalog:lista")

    client.force_login(emprendedora)
    respuesta_emprendedora = client.get(reverse("inicio"))
    assert respuesta_emprendedora.status_code == 302
    assert respuesta_emprendedora.url == reverse("alerts:panel")


@pytest.mark.django_db
def test_inicio_consulta_productos_en_un_numero_constante(client, django_assert_max_num_queries):
    for indice in range(1, 11):
        crear_producto_publico(indice)

    with django_assert_max_num_queries(2):
        respuesta = client.get(reverse("inicio"))

    assert respuesta.status_code == 200
    assert len(respuesta.context["destacados"]) == 4


@pytest.mark.django_db
def test_servicio_productos_destacados_respeta_limite():
    for indice in range(1, 4):
        crear_producto(
            nombre=f"Prenda {indice}",
            descripcion="Prenda artesanal hecha a mano",
            precio=Decimal("45000"),
            imagen=imagen(f"prenda-{indice}.png"),
            tipo=Producto.Tipo.DISPONIBLE,
            tiempo_produccion_dias=5,
            stock_producto=4,
        )

    assert len(productos_destacados(limite=2)) == 2
