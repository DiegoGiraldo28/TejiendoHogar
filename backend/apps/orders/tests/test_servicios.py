"""Servicios del proceso de pedidos: motor de fecha, creación, pago, estados y cancelación."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalog.models import Producto
from apps.inventory.models import Insumo, MovimientoInsumo
from apps.inventory.services import descontar_insumos, guardar_receta
from apps.orders.carrito import Bolsa
from apps.orders.models import DetallePedido, Pedido, RechazoPedido
from apps.orders.pagos import PasarelaSimulada, obtener_pasarela
from apps.orders.services import (
    PedidoYaConfirmado, cambiar_estado, cancelar_pedido, crear_pedido, desglose_fecha_entrega,
    estimar_fecha_entrega, pagar_y_confirmar, preparar_pedido_desde_bolsa,
)
from .ayudantes import DIRECCION, TELEFONO, SesionPrueba, disponible, otra_cliente, sobre_pedido

BASE = date(2026, 11, 10)
Estado = Pedido.Estado


def pedir(cliente, *lineas):
    return crear_pedido(
        cliente=cliente, lineas=[{"producto": p, "cantidad": c} for p, c in lineas],
        direccion=DIRECCION, telefono=TELEFONO,
    )


def confirmado(cliente, *lineas):
    return pagar_y_confirmar(pedido=pedir(cliente, *lineas), simular_exito=True, usuario=cliente)


# --- Motor de fecha (RNF-27) ---

@pytest.mark.django_db
def test_fecha_sin_cola_suma_dias_propios_y_alistamiento():
    vestido = sobre_pedido(dias=4)
    assert estimar_fecha_entrega(lineas=[{"producto": vestido, "cantidad": 2}], fecha_base=BASE) == BASE + timedelta(9)


@pytest.mark.django_db
def test_fecha_solo_con_disponibles_es_base_mas_uno():
    blusa = disponible(dias=7)
    assert estimar_fecha_entrega(lineas=[{"producto": blusa, "cantidad": 3}], fecha_base=BASE) == BASE + timedelta(1)


@pytest.mark.django_db
def test_fecha_con_cola_cuenta_confirmados_y_en_preparacion(cliente, emprendedora):
    vestido = sobre_pedido(dias=4, cantidad_insumo="100")
    en_preparacion = confirmado(cliente, (vestido, 2))
    cambiar_estado(pedido=en_preparacion, nuevo_estado=Estado.EN_PREPARACION, usuario=emprendedora)
    confirmado(cliente, (vestido, 1))
    pedir(cliente, (vestido, 3))
    entregado = confirmado(cliente, (vestido, 5))
    for estado in (Estado.EN_PREPARACION, Estado.LISTO, Estado.ENTREGADO):
        cambiar_estado(pedido=entregado, nuevo_estado=estado, usuario=emprendedora)
    cancelado = confirmado(cliente, (vestido, 1))
    cancelar_pedido(pedido=cancelado, usuario=emprendedora)

    # Cola: 2×4 (En preparación) + 1×4 (Confirmado) = 12; Pendiente, Entregado y Cancelado no cuentan.
    estimada = estimar_fecha_entrega(lineas=[{"producto": vestido, "cantidad": 1}], fecha_base=BASE)
    assert estimada == BASE + timedelta(days=12 + 4 + 1)


@pytest.mark.django_db
@pytest.mark.parametrize("cantidad_sobre, cantidad_disp, dias, esperado", [
    (1, 0, 1, 2), (1, 2, 3, 4), (3, 1, 5, 16), (10, 0, 2, 21),
])
def test_fecha_precision_total_en_casos_conocidos(cantidad_sobre, cantidad_disp, dias, esperado):
    lineas = [{"producto": sobre_pedido(dias=dias, cantidad_insumo="100"), "cantidad": cantidad_sobre}]
    if cantidad_disp:
        lineas.append({"producto": disponible(), "cantidad": cantidad_disp})
    assert (estimar_fecha_entrega(lineas=lineas, fecha_base=BASE) - BASE).days == esperado


@pytest.mark.django_db
def test_confirmar_fija_fecha_y_desglose_coherente(cliente):
    vestido = sobre_pedido(dias=4, cantidad_insumo="100")
    confirmado(cliente, (vestido, 2))
    pedido = confirmado(cliente, (vestido, 1), (disponible(), 1))
    hoy = timezone.localdate()
    assert pedido.fecha_estimada_entrega == hoy + timedelta(days=8 + 4 + 1)
    desglose = desglose_fecha_entrega(pedido=pedido)
    assert desglose == {
        "fecha_confirmacion": hoy, "dias_cola": 8, "dias_propios": 4, "dias_alistamiento": 1,
        "fecha_estimada": pedido.fecha_estimada_entrega,
    }
    total = desglose["dias_cola"] + desglose["dias_propios"] + desglose["dias_alistamiento"]
    assert desglose["fecha_confirmacion"] + timedelta(days=total) == pedido.fecha_estimada_entrega
    assert desglose_fecha_entrega(pedido=pedir(cliente, (vestido, 1))) is None


# --- Crear pedido ---

@pytest.mark.django_db
def test_crear_pedido_usa_precios_del_servidor_e_historial_inicial(cliente):
    blusa = disponible(precio="45000")
    blusa.precio = Decimal("1")  # precio manipulado fuera de la base de datos
    pedido = pedir(cliente, (blusa, 2))
    assert pedido.estado == Estado.PENDIENTE
    assert pedido.subtotal == Decimal("90000")
    assert pedido.detalles.get().precio_unitario == Decimal("45000")
    historial = pedido.historial.get()
    assert historial.estado_anterior is None and historial.estado_nuevo == Estado.PENDIENTE
    assert historial.usuario == cliente
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5  # crear no reserva ni descuenta


@pytest.mark.django_db
def test_precio_congelado_se_cobra_aunque_cambie_el_producto(cliente):
    blusa = disponible(precio="45000")
    pedido = pedir(cliente, (blusa, 1))
    Producto.objects.filter(pk=blusa.pk).update(precio=Decimal("99000"))
    pedido = pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    assert pedido.subtotal == Decimal("45000")
    assert pedido.detalles.get().precio_unitario == Decimal("45000")


@pytest.mark.django_db
def test_crear_pedido_registra_rechazo_por_stock_aunque_se_revierta(cliente):
    blusa = disponible(stock=2)
    with pytest.raises(ValidationError, match="unidades suficientes"):
        pedir(cliente, (blusa, 3))
    rechazo = RechazoPedido.objects.get()
    assert rechazo.motivo == RechazoPedido.Motivo.STOCK_INSUFICIENTE
    assert rechazo.pedido is None and rechazo.cliente == cliente
    assert not Pedido.objects.exists()


@pytest.mark.django_db
def test_crear_pedido_registra_rechazo_por_insumos_aunque_se_revierta(cliente):
    vestido = sobre_pedido(requerido="2", cantidad_insumo="3")
    with pytest.raises(ValidationError, match="insumos suficientes"):
        pedir(cliente, (vestido, 2))
    rechazo = RechazoPedido.objects.get()
    assert rechazo.motivo == RechazoPedido.Motivo.INSUMOS_INSUFICIENTES
    assert rechazo.pedido is None and rechazo.cliente == cliente
    assert not Pedido.objects.exists()


@pytest.mark.django_db
def test_crear_pedido_suma_insumos_compartidos_entre_lineas(cliente):
    vestido = sobre_pedido(nombre="Vestido", requerido="2", cantidad_insumo="5")
    insumo = vestido.receta.get().insumo
    falda = sobre_pedido(nombre="Falda", insumo=insumo, requerido="2")
    with pytest.raises(ValidationError):
        pedir(cliente, (vestido, 2), (falda, 1))
    assert RechazoPedido.objects.filter(motivo=RechazoPedido.Motivo.INSUMOS_INSUFICIENTES).count() == 1


@pytest.mark.django_db
def test_crear_pedido_exige_entrega_y_lineas(cliente, emprendedora):
    blusa = disponible()
    with pytest.raises(ValidationError) as error:
        crear_pedido(cliente=cliente, lineas=[{"producto": blusa, "cantidad": 1}], direccion=" ", telefono="")
    assert set(error.value.message_dict) == {"direccion", "telefono"}
    with pytest.raises(ValidationError) as error:
        crear_pedido(cliente=cliente, lineas=[{"producto": blusa, "cantidad": 1}], direccion="Casa", telefono="12")
    assert "telefono" in error.value.message_dict
    with pytest.raises(ValidationError, match="vacía"):
        crear_pedido(cliente=cliente, lineas=[], direccion=DIRECCION, telefono=TELEFONO)
    with pytest.raises(ValidationError, match="Solo una Cliente"):
        pedir(emprendedora, (blusa, 1))


@pytest.mark.django_db
def test_crear_pedido_respeta_topes_y_productos_activos(cliente):
    vestido = sobre_pedido(cantidad_insumo="100")
    with pytest.raises(ValidationError, match="máximo 10"):
        pedir(cliente, (vestido, 11))
    with pytest.raises(ValidationError, match="mínima es 1"):
        pedir(cliente, (vestido, 0))
    blusa = disponible(stock=2)
    Producto.objects.filter(pk=blusa.pk).update(activo=False)
    with pytest.raises(ValidationError, match="ya no está disponible"):
        pedir(cliente, (blusa, 1))


# --- Pagar y confirmar ---

@pytest.mark.django_db
def test_pago_exitoso_descuenta_stock_e_insumos_y_confirma(cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(dias=4, requerido="2", cantidad_insumo="10")
    insumo = vestido.receta.get().insumo
    pedido = confirmado(cliente, (blusa, 2), (vestido, 3))

    assert pedido.estado == Estado.CONFIRMADO
    assert pedido.pago_simulado_estado == Pedido.PagoSimulado.EXITOSO
    assert pedido.fecha_confirmacion and pedido.fecha_estimada_entrega
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 3
    assert Insumo.objects.get(pk=insumo.pk).cantidad_disponible == Decimal("4")
    movimiento = MovimientoInsumo.objects.get(pedido=pedido)
    assert (movimiento.tipo_movimiento, movimiento.cantidad) == ("Descuento", Decimal("6"))
    lineas = {d.producto_id: d for d in pedido.detalles.all()}
    assert (lineas[blusa.pk].origen, lineas[blusa.pk].dias_produccion) == ("Stock", 0)
    assert (lineas[vestido.pk].origen, lineas[vestido.pk].dias_produccion) == ("Confeccion", 4)
    assert list(pedido.historial.values_list("estado_anterior", "estado_nuevo")) == [
        (None, "Pendiente"), ("Pendiente", "Confirmado"),
    ]


@pytest.mark.django_db
def test_pago_fallido_deja_pendiente_sin_descontar_y_reintento_confirma(cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(cantidad_insumo="10")
    pedido = pedir(cliente, (blusa, 1), (vestido, 1))

    fallido = pagar_y_confirmar(pedido=pedido, simular_exito=False, usuario=cliente)
    assert fallido.estado == Estado.PENDIENTE
    assert fallido.pago_simulado_estado == Pedido.PagoSimulado.FALLIDO
    assert fallido.resultado_pago.mensaje == "Fondos insuficientes (simulado)."
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5
    assert not MovimientoInsumo.objects.filter(pedido=pedido).exists()
    assert pedido.historial.count() == 1

    exitoso = pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    assert exitoso.estado == Estado.CONFIRMADO
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 4


@pytest.mark.django_db
def test_rechazo_al_confirmar_persiste_y_el_pedido_sigue_pendiente(cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(requerido="2", cantidad_insumo="4")
    pedido = pedir(cliente, (blusa, 2), (vestido, 2))
    Insumo.objects.filter(pk=vestido.receta.get().insumo_id).update(cantidad_disponible=Decimal("3"))

    with pytest.raises(ValidationError, match="insumos suficientes"):
        pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)

    rechazo = RechazoPedido.objects.get()
    assert rechazo.pedido == pedido and rechazo.motivo == RechazoPedido.Motivo.INSUMOS_INSUFICIENTES
    pedido.refresh_from_db()
    assert pedido.estado == Estado.PENDIENTE and pedido.pago_simulado_estado is None
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5
    assert not MovimientoInsumo.objects.filter(pedido=pedido).exists()


@pytest.mark.django_db
def test_rechazo_al_confirmar_por_stock(cliente):
    blusa = disponible(stock=2)
    pedido = pedir(cliente, (blusa, 2))
    Producto.objects.filter(pk=blusa.pk).update(stock_producto=1)
    with pytest.raises(ValidationError):
        pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    assert RechazoPedido.objects.get().motivo == RechazoPedido.Motivo.STOCK_INSUFICIENTE


@pytest.mark.django_db
def test_doble_pago_confirma_y_descuenta_una_sola_vez(cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(requerido="1", cantidad_insumo="10")
    pedido = pedir(cliente, (blusa, 1), (vestido, 1))
    pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    with pytest.raises(PedidoYaConfirmado, match="Tu pedido ya fue confirmado"):
        pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 4
    assert MovimientoInsumo.objects.filter(pedido=pedido).count() == 1
    assert pedido.historial.filter(estado_nuevo=Estado.CONFIRMADO).count() == 1


@pytest.mark.django_db
def test_pagar_exige_dueña_y_pedido_pendiente(cliente, emprendedora):
    pedido = pedir(cliente, (disponible(), 1))
    with pytest.raises(ValidationError, match="dueña"):
        pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=otra_cliente())
    cancelar_pedido(pedido=pedido, usuario=cliente)
    with pytest.raises(ValidationError, match="ya no está pendiente"):
        pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)


# --- Cambiar estado ---

@pytest.mark.django_db
def test_camino_completo_hasta_entregado(cliente, emprendedora):
    pedido = confirmado(cliente, (disponible(), 1))
    for estado in (Estado.EN_PREPARACION, Estado.LISTO, Estado.ENTREGADO):
        pedido = cambiar_estado(pedido=pedido, nuevo_estado=estado, usuario=emprendedora)
        assert pedido.estado == estado
    assert pedido.fecha_entrega_real == timezone.localdate()
    assert pedido.historial.count() == 5
    assert pedido.historial.last().usuario == emprendedora


@pytest.mark.django_db
def test_cambiar_estado_rechaza_transiciones_invalidas(cliente, emprendedora):
    pendiente = pedir(cliente, (disponible(nombre="A"), 1))
    with pytest.raises(ValidationError, match="No se puede pasar"):
        cambiar_estado(pedido=pendiente, nuevo_estado=Estado.EN_PREPARACION, usuario=emprendedora)
    pedido = confirmado(cliente, (disponible(nombre="B"), 1))
    with pytest.raises(ValidationError, match="No se puede pasar"):
        cambiar_estado(pedido=pedido, nuevo_estado=Estado.LISTO, usuario=emprendedora)
    with pytest.raises(ValidationError, match="estado válido"):
        cambiar_estado(pedido=pedido, nuevo_estado="Perdido", usuario=emprendedora)
    with pytest.raises(ValidationError, match="Solo la Emprendedora"):
        cambiar_estado(pedido=pedido, nuevo_estado=Estado.EN_PREPARACION, usuario=cliente)


# --- Cancelar ---

@pytest.mark.django_db
def test_cancelar_pendiente_no_devuelve_nada(cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(cantidad_insumo="10")
    pedido = cancelar_pedido(pedido=pedir(cliente, (blusa, 1), (vestido, 1)), usuario=cliente)
    assert pedido.estado == Estado.CANCELADO and pedido.fecha_cancelacion
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5
    assert not MovimientoInsumo.objects.filter(pedido=pedido).exists()
    assert pedido.historial.last().estado_anterior == Estado.PENDIENTE


@pytest.mark.django_db
def test_cancelar_confirmado_devuelve_exactamente_lo_descontado(cliente, emprendedora):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(requerido="2", cantidad_insumo="10")
    insumo = vestido.receta.get().insumo
    pedido = confirmado(cliente, (blusa, 2), (vestido, 2))
    guardar_receta(producto=vestido, lineas=[{"insumo": insumo, "cantidad_requerida": Decimal("7")}])

    pedido = cancelar_pedido(pedido=pedido, usuario=emprendedora)

    assert pedido.estado == Estado.CANCELADO
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5
    assert Insumo.objects.get(pk=insumo.pk).cantidad_disponible == Decimal("10")
    devolucion = MovimientoInsumo.objects.get(pedido=pedido, tipo_movimiento="Devolucion")
    assert devolucion.cantidad == Decimal("4")


@pytest.mark.django_db
def test_reglas_de_cancelacion_por_rol_y_estado(cliente, emprendedora):
    pendiente = pedir(cliente, (disponible(nombre="A"), 1))
    with pytest.raises(ValidationError, match="tus propios pedidos"):
        cancelar_pedido(pedido=pendiente, usuario=otra_cliente())
    confirmado_cliente = confirmado(cliente, (disponible(nombre="B"), 1))
    with pytest.raises(ValidationError, match="en espera de pago"):
        cancelar_pedido(pedido=confirmado_cliente, usuario=cliente)
    cambiar_estado(pedido=confirmado_cliente, nuevo_estado=Estado.EN_PREPARACION, usuario=emprendedora)
    with pytest.raises(ValidationError, match="Pendientes o Confirmados"):
        cancelar_pedido(pedido=confirmado_cliente, usuario=emprendedora)
    operaria = Usuario.objects.create_user("op@example.com", "ClaveFuerte-2026", nombre="Op", rol="Operaria")
    with pytest.raises(ValidationError, match="permiso"):
        cancelar_pedido(pedido=pendiente, usuario=operaria)
    assert cancelar_pedido(pedido=pendiente, usuario=emprendedora).estado == Estado.CANCELADO


# --- Bolsa y reutilización del Pendiente ---

@pytest.mark.django_db
def test_preparar_pedido_reutiliza_sin_cambios(cliente):
    bolsa = Bolsa(SesionPrueba())
    bolsa.agregar(producto=disponible(), cantidad=2)
    primero = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    segundo = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=f" {DIRECCION} ",
                                          telefono=TELEFONO)
    assert primero.pk == segundo.pk
    assert Pedido.objects.count() == 1


@pytest.mark.django_db
def test_preparar_pedido_reemplaza_si_cambia_la_bolsa_o_la_entrega(cliente):
    blusa = disponible()
    bolsa = Bolsa(SesionPrueba())
    bolsa.agregar(producto=blusa, cantidad=1)
    primero = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    bolsa.actualizar(producto=blusa, cantidad=2)
    segundo = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    tercero = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion="Otra dirección",
                                          telefono=TELEFONO)
    assert len({primero.pk, segundo.pk, tercero.pk}) == 3
    assert Pedido.objects.get(pk=primero.pk).estado == Estado.CANCELADO
    assert Pedido.objects.get(pk=segundo.pk).estado == Estado.CANCELADO
    assert bolsa.pedido_pendiente_id == tercero.pk


@pytest.mark.django_db
def test_preparar_pedido_ignora_pendiente_que_ya_no_esta_vigente(cliente):
    bolsa = Bolsa(SesionPrueba())
    bolsa.agregar(producto=disponible(), cantidad=1)
    pagado = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    pagar_y_confirmar(pedido=pagado, simular_exito=True, usuario=cliente)  # pagado en otra pestaña
    nuevo = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    assert nuevo.pk != pagado.pk
    assert Pedido.objects.get(pk=pagado.pk).estado == Estado.CONFIRMADO

    ajeno = pedir(otra_cliente(), (disponible(nombre="Ajeno"), 1))
    bolsa.pedido_pendiente_id = ajeno.pk
    propio = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    assert propio.cliente == cliente
    assert Pedido.objects.get(pk=ajeno.pk).estado == Estado.PENDIENTE


@pytest.mark.django_db
def test_preparar_pedido_continua_si_no_puede_cancelar_el_anterior(cliente, monkeypatch):
    blusa = disponible()
    bolsa = Bolsa(SesionPrueba())
    bolsa.agregar(producto=blusa, cantidad=1)
    primero = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)
    bolsa.actualizar(producto=blusa, cantidad=2)

    def pagado_en_otra_pestana(*, pedido, usuario):
        raise ValidationError("Solo puedes cancelar pedidos que están en espera de pago.")

    avisos = []
    monkeypatch.setattr("apps.orders.services.cancelar_pedido", pagado_en_otra_pestana)
    monkeypatch.setattr("apps.orders.services.logger.warning", lambda mensaje, *args: avisos.append(mensaje % args))
    nuevo = preparar_pedido_desde_bolsa(cliente=cliente, bolsa=bolsa, direccion=DIRECCION, telefono=TELEFONO)

    assert nuevo.pk != primero.pk and nuevo.estado == Estado.PENDIENTE
    assert bolsa.pedido_pendiente_id == nuevo.pk
    assert Pedido.objects.get(pk=primero.pk).estado == Estado.PENDIENTE
    assert avisos == [f"No se pudo cancelar el pedido pendiente {primero.pk} al reemplazarlo por {nuevo.pk}."]


@pytest.mark.django_db
def test_bolsa_agrega_actualiza_quita_y_respeta_topes():
    sesion = SesionPrueba()
    bolsa = Bolsa(sesion)
    blusa = disponible(stock=2)
    vestido = sobre_pedido(cantidad_insumo="100")
    assert bolsa.agregar(producto=blusa) == 1
    assert bolsa.agregar(producto=blusa) == 2
    with pytest.raises(ValidationError, match="Solo hay 2"):
        bolsa.agregar(producto=blusa)
    bolsa.actualizar(producto=vestido, cantidad=10)
    with pytest.raises(ValidationError, match="máximo 10"):
        bolsa.agregar(producto=vestido)
    with pytest.raises(ValidationError, match="cantidad válida"):
        bolsa.actualizar(producto=vestido, cantidad="x")
    assert bolsa.total_unidades == 12
    assert sum(linea.subtotal for linea in bolsa.lineas()) == blusa.precio * 2 + vestido.precio * 10
    bolsa.actualizar(producto=vestido, cantidad=0)
    bolsa.quitar(producto_id=blusa.pk)
    assert bolsa.lineas() == [] and sesion.modified
    Producto.objects.filter(pk=blusa.pk).update(activo=False)
    blusa.refresh_from_db()
    with pytest.raises(ValidationError, match="ya no está disponible"):
        bolsa.agregar(producto=blusa)


@pytest.mark.django_db
def test_bolsa_descarta_inactivos_y_guarda_borrador():
    bolsa = Bolsa(SesionPrueba())
    blusa = disponible()
    bolsa.agregar(producto=blusa, cantidad=1)
    bolsa.guardar_borrador(direccion="Casa", telefono="3001234567")
    Producto.objects.filter(pk=blusa.pk).update(activo=False)
    assert bolsa.lineas() == [] and bolsa.total_unidades == 0
    assert bolsa.borrador() == {"direccion": "Casa", "telefono": "3001234567"}
    bolsa.pedido_pendiente_id = 5
    bolsa.vaciar()
    assert bolsa.borrador() == {} and bolsa.pedido_pendiente_id is None


# --- Pasarela e inventario ---

def test_pasarela_configurada_es_la_simulada(settings):
    assert isinstance(obtener_pasarela(), PasarelaSimulada)
    settings.PASARELA_PAGO = "desconocida"
    with pytest.raises(ImproperlyConfigured):
        obtener_pasarela()


@pytest.mark.django_db
def test_descontar_insumos_rechaza_producto_sin_receta_o_sin_existencias(cliente):
    pedido = pedir(cliente, (disponible(), 1))
    sin_receta = disponible(nombre="Sin receta")
    with pytest.raises(ValidationError, match="no tiene receta"):
        descontar_insumos(pedido=pedido, producto=sin_receta, cantidad=1)
    vestido = sobre_pedido(requerido="5", cantidad_insumo="4")
    with pytest.raises(ValidationError, match="No hay suficiente"):
        descontar_insumos(pedido=pedido, producto=vestido, cantidad=1)
    assert DetallePedido.objects.count() == 1
