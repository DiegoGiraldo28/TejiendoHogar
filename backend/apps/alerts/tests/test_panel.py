"""Pruebas del panel de la emprendedora."""
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.catalog.models import Producto
from apps.catalog.services import crear_producto
from apps.catalog.tests.test_catalog import imagen
from apps.inventory.models import Insumo
from apps.inventory.services import crear_insumo


@pytest.fixture(autouse=True)
def media_temporal(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


@pytest.mark.django_db
def test_panel_muestra_conteos_y_elementos_con_stock_bajo(client, emprendedora):
    producto = crear_producto(
        nombre="Blusa", descripcion="Tejida", precio=Decimal("100"), imagen=imagen(),
        tipo=Producto.Tipo.DISPONIBLE, tiempo_produccion_dias=3, stock_producto=0, stock_minimo=1,
    )
    insumo = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=0, stock_minimo=1)
    client.force_login(emprendedora)
    respuesta = client.get(reverse("alerts:panel"))
    assert respuesta.status_code == 200
    assert respuesta.context["productos_activos"] == 1
    assert list(respuesta.context["insumos_bajos"]) == [insumo]
    assert list(respuesta.context["productos_bajos"]) == [producto]


@pytest.mark.django_db
def test_panel_no_tiene_actividad_sin_productos(client, emprendedora):
    client.force_login(emprendedora)
    respuesta = client.get(reverse("alerts:panel"))
    assert respuesta.context["porcentaje_sin_actividad"] == 0
