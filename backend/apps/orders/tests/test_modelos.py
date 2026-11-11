"""Restricciones del esquema, propiedades de presentación y triggers de pedidos."""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone

from apps.inventory.models import Insumo, MovimientoInsumo
from apps.orders.models import DetallePedido, HistorialEstadoPedido, Pedido, RechazoPedido
from apps.orders.services import crear_pedido
from .ayudantes import DIRECCION, TELEFONO, disponible

AHORA = timezone.now()


def pedido_base(cliente, **cambios):
    datos = {
        "cliente": cliente, "estado": Pedido.Estado.PENDIENTE, "subtotal": Decimal("1000"),
        "direccion_entrega": DIRECCION, "telefono_contacto": TELEFONO,
    }
    datos.update(cambios)
    return datos


def falla_insert(modelo, **datos):
    with pytest.raises(IntegrityError), transaction.atomic():
        modelo.objects.create(**datos)


CONFIRMADO_VALIDO = {
    "estado": Pedido.Estado.CONFIRMADO, "pago_simulado_estado": "Exitoso",
    "fecha_confirmacion": AHORA, "fecha_estimada_entrega": date(2026, 12, 1),
}


@pytest.mark.django_db
@pytest.mark.parametrize("cambios", [
    {"estado": "Enviado"},
    {"pago_simulado_estado": "Rechazado"},
    {"subtotal": Decimal("-1")},
    {"direccion_entrega": "   "},
    {"telefono_contacto": "abc"},
    {**CONFIRMADO_VALIDO, "pago_simulado_estado": None},
    {**CONFIRMADO_VALIDO, "pago_simulado_estado": "Fallido"},
    {**CONFIRMADO_VALIDO, "fecha_estimada_entrega": None},
    {**CONFIRMADO_VALIDO, "fecha_confirmacion": None},
    {"estado": Pedido.Estado.CANCELADO},
    {"fecha_cancelacion": AHORA},
    {**CONFIRMADO_VALIDO, "estado": Pedido.Estado.ENTREGADO},
    {"fecha_entrega_real": date(2026, 12, 1)},
], ids=[
    "estado", "pago_estado", "subtotal", "direccion", "telefono", "pago_exitoso_nulo", "pago_exitoso_fallido",
    "confirmado_sin_estimada", "confirmado_sin_confirmacion", "cancelado_sin_fecha", "fecha_cancelacion_pendiente",
    "entregado_sin_fecha", "fecha_entrega_pendiente",
])
def test_restricciones_de_pedido_rechazan_datos_invalidos(cliente, cambios):
    falla_insert(Pedido, **pedido_base(cliente, **cambios))


@pytest.mark.django_db
def test_restricciones_de_pedido_aceptan_estados_coherentes(cliente):
    Pedido.objects.create(**pedido_base(cliente))
    Pedido.objects.create(**pedido_base(cliente, **CONFIRMADO_VALIDO))
    Pedido.objects.create(**pedido_base(cliente, estado=Pedido.Estado.CANCELADO, fecha_cancelacion=AHORA))
    assert Pedido.objects.count() == 3


@pytest.mark.django_db
def test_restricciones_tienen_mensajes_en_espanol(cliente):
    pedido = Pedido(**pedido_base(cliente, estado=Pedido.Estado.CONFIRMADO))
    with pytest.raises(ValidationError) as error:
        pedido.full_clean()
    mensajes = " ".join(error.value.messages)
    assert "Solo un pago exitoso permite confirmar el pedido." in mensajes
    assert "fecha de confirmación y fecha estimada" in mensajes


@pytest.mark.django_db
@pytest.mark.parametrize("cambios", [
    {"cantidad": 0},
    {"precio_unitario": Decimal("-1")},
    {"origen": "Bodega", "dias_produccion": 0},
    {"origen": "Stock", "dias_produccion": -1},
    {"origen": "Stock"},
    {"dias_produccion": 2},
], ids=["cantidad", "precio", "origen", "dias", "origen_sin_dias", "dias_sin_origen"])
def test_restricciones_de_detalle_rechazan_datos_invalidos(cliente, cambios):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    datos = {"pedido": pedido, "producto": disponible(), "cantidad": 1, "precio_unitario": Decimal("10")}
    datos.update(cambios)
    falla_insert(DetallePedido, **datos)


@pytest.mark.django_db
def test_detalle_no_repite_producto_en_el_pedido(cliente):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    producto = disponible()
    DetallePedido.objects.create(pedido=pedido, producto=producto, cantidad=1, precio_unitario=Decimal("1"))
    falla_insert(DetallePedido, pedido=pedido, producto=producto, cantidad=2, precio_unitario=Decimal("1"))


@pytest.mark.django_db
def test_restricciones_de_historial_y_rechazo(cliente):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    falla_insert(HistorialEstadoPedido, pedido=pedido, usuario=cliente, estado_nuevo="Perdido")
    falla_insert(HistorialEstadoPedido, pedido=pedido, usuario=cliente, estado_anterior="Perdido",
                 estado_nuevo=Pedido.Estado.PENDIENTE)
    falla_insert(RechazoPedido, cliente=cliente, motivo="Otro")


@pytest.mark.django_db
def test_movimiento_exige_pedido_segun_su_tipo(cliente):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    insumo = Insumo.objects.create(nombre="Lino", unidad_medida="metros")
    falla_insert(MovimientoInsumo, insumo=insumo, pedido=pedido, tipo_movimiento="Entrada", cantidad=1)
    falla_insert(MovimientoInsumo, insumo=insumo, tipo_movimiento="Descuento", cantidad=1)
    falla_insert(MovimientoInsumo, insumo=insumo, tipo_movimiento="Devolucion", cantidad=1)
    MovimientoInsumo.objects.create(insumo=insumo, pedido=pedido, tipo_movimiento="Descuento", cantidad=1)
    MovimientoInsumo.objects.create(insumo=insumo, tipo_movimiento="Entrada", cantidad=1)


@pytest.mark.django_db
def test_numero_visible_y_nombres_de_estado(cliente):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    assert pedido.numero_visible == f"#TH-{pedido.pk:04d}"
    assert Pedido(id_pedido=12).numero_visible == "#TH-0012"
    assert pedido.estado_cliente == "En espera de pago"
    assert pedido.estado_emprendedora == "Pendiente"
    pedido.estado = Pedido.Estado.EN_PREPARACION
    assert pedido.estado_cliente == "En preparación"  # sin líneas de Confeccion
    assert pedido.estado_emprendedora == "En preparación"
    pedido.estado = Pedido.Estado.LISTO
    assert pedido.estado_cliente == "Listo y empaque"


@pytest.mark.django_db
def test_trigger_rechaza_transicion_invalida_en_la_base_de_datos(cliente):
    pedido = Pedido.objects.create(**pedido_base(cliente))
    with pytest.raises(IntegrityError, match="Transición de estado no permitida"), transaction.atomic():
        Pedido.objects.filter(pk=pedido.pk).update(estado=Pedido.Estado.EN_PREPARACION)
    Pedido.objects.filter(pk=pedido.pk).update(estado=Pedido.Estado.CANCELADO, fecha_cancelacion=AHORA)
    with pytest.raises(IntegrityError), transaction.atomic():
        Pedido.objects.filter(pk=pedido.pk).update(estado=Pedido.Estado.PENDIENTE, fecha_cancelacion=None)


@pytest.mark.django_db
def test_trigger_hace_inmutable_el_historial(cliente):
    pedido = crear_pedido(cliente=cliente, lineas=[{"producto": disponible(), "cantidad": 1}],
                          direccion=DIRECCION, telefono=TELEFONO)
    registro = pedido.historial.get()
    with pytest.raises(DatabaseError, match="inmutable"), transaction.atomic():
        HistorialEstadoPedido.objects.filter(pk=registro.pk).update(estado_nuevo=Pedido.Estado.CANCELADO)
    with pytest.raises(DatabaseError, match="inmutable"), transaction.atomic():
        HistorialEstadoPedido.objects.filter(pk=registro.pk).delete()
    assert HistorialEstadoPedido.objects.filter(pk=registro.pk, estado_nuevo=Pedido.Estado.PENDIENTE).exists()
