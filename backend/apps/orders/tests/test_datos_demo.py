"""Pruebas de los pedidos de ejemplo que crea cargar_datos_demo."""
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.orders.models import Pedido


def cargar():
    salida = StringIO()
    call_command("cargar_datos_demo", stdout=salida)
    return salida.getvalue()


@pytest.mark.django_db
def test_sin_cliente_omite_los_pedidos_y_avisa():
    salida = cargar()
    assert "No hay ninguna cuenta Cliente" in salida
    assert not Pedido.objects.exists()
    assert not get_user_model().objects.exists()


@pytest.mark.django_db
def test_crea_cuatro_pedidos_en_estados_distintos_para_la_primera_cliente(cliente, emprendedora):
    usuarios = get_user_model().objects.count()
    salida = cargar()
    assert f"Pedidos de ejemplo creados para {cliente.correo}: 4." in salida
    assert sorted(Pedido.objects.filter(cliente=cliente).values_list("estado", flat=True)) == sorted(
        ["Pendiente", "Confirmado", "En_preparacion", "Entregado"],
    )
    assert Pedido.objects.get(estado="En_preparacion").detalles.get().origen == "Confeccion"
    assert Pedido.objects.get(estado="En_preparacion").movimientos_insumo.exists()

    assert "ya tiene pedidos" in cargar()
    assert Pedido.objects.count() == 4
    assert get_user_model().objects.count() == usuarios


@pytest.mark.django_db
def test_sin_emprendedora_los_pedidos_quedan_confirmados(cliente):
    salida = cargar()
    assert "No hay Emprendedora" in salida
    assert sorted(Pedido.objects.values_list("estado", flat=True)) == sorted(
        ["Pendiente", "Confirmado", "Confirmado", "Confirmado"],
    )
