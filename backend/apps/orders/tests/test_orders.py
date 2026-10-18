"""Pruebas de autorización y validación de pedidos provisionales."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Producto
from apps.catalog.services import crear_producto
from apps.catalog.tests.test_catalog import imagen
from apps.inventory.models import Insumo
from apps.inventory.services import crear_insumo, guardar_receta


def producto(*, tipo=Producto.Tipo.DISPONIBLE, stock=3):
    return crear_producto(
        nombre="Blusa de lino", descripcion="Tejida a mano", precio=Decimal("45000"),
        imagen=imagen("blusa.png"), tipo=tipo, tiempo_produccion_dias=5,
        stock_producto=stock,
    )


@pytest.mark.django_db
def test_cliente_puede_ver_resumen_sin_crear_pedido(client, cliente):
    prenda = producto()
    client.force_login(cliente)

    respuesta = client.post(reverse("orders:en_proceso"), {"producto_id": prenda.pk, "cantidad": 2})

    assert respuesta.status_code == 200
    assert b"Pedido en proceso" in respuesta.content
    assert respuesta.context["subtotal"] == Decimal("90000")
    assert not hasattr(prenda, "pedido_set")


@pytest.mark.django_db
def test_pedido_anónimo_va_a_login_con_next(client):
    respuesta = client.post(reverse("orders:en_proceso"), {})
    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('accounts:login')}?next={reverse('orders:en_proceso')}"


@pytest.mark.django_db
def test_pedido_rechaza_emprendedora_y_metodo_get(client, emprendedora, cliente):
    url = reverse("orders:en_proceso")
    client.force_login(emprendedora)
    assert client.post(url, {}).status_code == 403
    client.force_login(cliente)
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_pedido_rechaza_cantidad_mayor_al_stock(client, cliente):
    prenda = producto(stock=2)
    client.force_login(cliente)
    respuesta = client.post(reverse("orders:en_proceso"), {"producto_id": prenda.pk, "cantidad": 3})
    assert respuesta.status_code == 400
    assert b"supera las unidades disponibles" in respuesta.content


@pytest.mark.django_db
def test_pedido_rechaza_cantidad_menor_a_uno(client, cliente):
    prenda = producto()
    client.force_login(cliente)
    respuesta = client.post(reverse("orders:en_proceso"), {"producto_id": prenda.pk, "cantidad": 0})
    assert respuesta.status_code == 400
    assert respuesta.context["form"]["cantidad"].errors


@pytest.mark.django_db
def test_pedido_rechaza_producto_inactivo(client, cliente):
    prenda = producto()
    prenda.activo = False
    prenda.save(update_fields=["activo"])
    client.force_login(cliente)
    respuesta = client.post(reverse("orders:en_proceso"), {"producto_id": prenda.pk, "cantidad": 1})
    assert respuesta.status_code == 400
    assert b"ya no est\xc3\xa1 disponible" in respuesta.content


@pytest.mark.django_db
def test_pedido_sobre_pedido_no_usa_stock_de_producto(client, cliente):
    prenda = producto(tipo=Producto.Tipo.SOBRE_PEDIDO, stock=0)
    insumo = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS)
    guardar_receta(producto=prenda, lineas=[{"insumo": insumo, "cantidad_requerida": 1}])
    prenda.activo = True
    prenda.save(update_fields=["activo"])
    client.force_login(cliente)
    respuesta = client.post(reverse("orders:en_proceso"), {"producto_id": prenda.pk, "cantidad": 10})
    assert respuesta.status_code == 200
    assert respuesta.context["subtotal"] == Decimal("450000")
