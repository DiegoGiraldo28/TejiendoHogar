"""Concurrencia (RNF-08): confirmaciones simultáneas con bloqueos reales de PostgreSQL."""
import threading
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection

from apps.catalog.models import Producto
from apps.inventory.models import Insumo, MovimientoInsumo
from apps.orders.models import Pedido, RechazoPedido
from apps.orders.services import PedidoYaConfirmado, crear_pedido, pagar_y_confirmar
from .ayudantes import DIRECCION, TELEFONO, disponible, otra_cliente, sobre_pedido


def en_paralelo(*funciones):
    """Ejecuta las funciones a la vez en hilos y devuelve el resultado o la excepción de cada una."""
    barrera = threading.Barrier(len(funciones))
    resultados = [None] * len(funciones)

    def correr(indice, funcion):
        try:
            barrera.wait()
            resultados[indice] = funcion()
        except Exception as error:  # noqa: BLE001 - se devuelve para revisarla en la prueba
            resultados[indice] = error
        finally:
            connection.close()

    hilos = [threading.Thread(target=correr, args=(i, f)) for i, f in enumerate(funciones)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)
    return resultados


@pytest.mark.django_db(transaction=True)
def test_dos_confirmaciones_compiten_por_el_ultimo_insumo(cliente):
    vestido = sobre_pedido(requerido="1", cantidad_insumo="1")
    insumo = vestido.receta.get().insumo
    segunda = otra_cliente()
    pedidos = [
        crear_pedido(cliente=duena, lineas=[{"producto": vestido, "cantidad": 1}],
                     direccion=DIRECCION, telefono=TELEFONO)
        for duena in (cliente, segunda)
    ]

    resultados = en_paralelo(*[
        (lambda p=p: pagar_y_confirmar(pedido=p, simular_exito=True, usuario=p.cliente)) for p in pedidos
    ])

    assert sum(isinstance(r, Pedido) for r in resultados) == 1
    assert sum(isinstance(r, ValidationError) for r in resultados) == 1
    assert Pedido.objects.filter(estado=Pedido.Estado.CONFIRMADO).count() == 1
    assert Pedido.objects.filter(estado=Pedido.Estado.PENDIENTE).count() == 1
    assert Insumo.objects.get(pk=insumo.pk).cantidad_disponible == Decimal("0")
    assert MovimientoInsumo.objects.filter(tipo_movimiento="Descuento").count() == 1
    assert RechazoPedido.objects.filter(pedido__isnull=False).count() == 1


@pytest.mark.django_db(transaction=True)
def test_doble_envio_simultaneo_descuenta_una_sola_vez(cliente):
    blusa = disponible(stock=3)
    pedido = crear_pedido(cliente=cliente, lineas=[{"producto": blusa, "cantidad": 2}],
                          direccion=DIRECCION, telefono=TELEFONO)

    resultados = en_paralelo(
        lambda: pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente),
        lambda: pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente),
    )

    assert sum(isinstance(r, Pedido) for r in resultados) == 1
    assert sum(isinstance(r, PedidoYaConfirmado) for r in resultados) == 1
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 1
    assert Pedido.objects.get(pk=pedido.pk).historial.filter(estado_nuevo=Pedido.Estado.CONFIRMADO).count() == 1
