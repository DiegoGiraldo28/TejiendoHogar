"""Reglas de negocio del proceso de pedidos con pago simulado."""
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, QuerySet, Sum
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalog.models import Producto
from apps.common.constants import DIAS_ALISTAMIENTO
from apps.common.validators import validar_telefono
from apps.inventory.models import Insumo, MovimientoInsumo, ProductoInsumo
from apps.inventory.services import (
    calcular_requerimiento, descontar_insumos, devolver_insumos, validar_disponibilidad,
)
from .carrito import Bolsa, validar_cantidad
from .models import (
    ESTADOS_ACEPTADOS, DetallePedido, HistorialEstadoPedido, Pedido, RechazoPedido, nombre_estado,
)
from .pagos import obtener_pasarela

logger = logging.getLogger(__name__)

Estado = Pedido.Estado
ESTADOS_EN_COLA = [Estado.CONFIRMADO, Estado.EN_PREPARACION]
SIGUIENTE_ESTADO = {
    Estado.CONFIRMADO: Estado.EN_PREPARACION,
    Estado.EN_PREPARACION: Estado.LISTO,
    Estado.LISTO: Estado.ENTREGADO,
}


class PedidoYaConfirmado(ValidationError):
    """El pedido ya se pagó y confirmó: un segundo envío del pago no hace nada."""


class _SinExistencias(Exception):
    """Falta stock o insumos; se convierte en RechazoPedido fuera de la transacción revertida."""

    def __init__(self, motivo: str, mensaje: str):
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje


def _normalizar(lineas: Iterable[Any]) -> list[tuple[Producto, int]]:
    """Acepta LineaBolsa, DetallePedido o diccionarios con producto y cantidad."""
    normalizadas = []
    for linea in lineas:
        if isinstance(linea, dict):
            normalizadas.append((linea["producto"], int(linea["cantidad"])))
        else:
            normalizadas.append((linea.producto, int(linea.cantidad)))
    return normalizadas


def _verificar_existencias(lineas: list[tuple[Producto, int]]) -> None:
    """Valida stock y la suma de insumos de todas las líneas; lanza _SinExistencias si falta algo."""
    for producto, cantidad in lineas:
        if producto.tipo == Producto.Tipo.DISPONIBLE:
            disponible, _ = validar_disponibilidad(producto=producto, cantidad=cantidad)
            if not disponible:
                raise _SinExistencias(
                    RechazoPedido.Motivo.STOCK_INSUFICIENTE,
                    f"No hay unidades suficientes de {producto.nombre}.",
                )
    requeridos: dict[int, Decimal] = {}
    insumos: dict[int, Insumo] = {}
    for producto, cantidad in lineas:
        if producto.tipo != Producto.Tipo.SOBRE_PEDIDO:
            continue
        requerimiento = calcular_requerimiento(producto=producto, cantidad=cantidad)
        if not requerimiento:
            raise _SinExistencias(
                RechazoPedido.Motivo.INSUMOS_INSUFICIENTES, f"{producto.nombre} no se puede confeccionar por ahora.",
            )
        for insumo, cantidad_insumo in requerimiento.items():
            insumos[insumo.pk] = insumo
            requeridos[insumo.pk] = requeridos.get(insumo.pk, Decimal("0")) + cantidad_insumo
    for insumo_id, requerido in requeridos.items():
        if requerido > insumos[insumo_id].cantidad_disponible:
            raise _SinExistencias(
                RechazoPedido.Motivo.INSUMOS_INSUFICIENTES,
                "No hay insumos suficientes para confeccionar tu pedido en este momento.",
            )


def _registrar_rechazo(*, cliente: Usuario, pedido: Pedido | None, error: _SinExistencias) -> None:
    RechazoPedido.objects.create(cliente=cliente, pedido=pedido, motivo=error.motivo)
    logger.warning(
        "Pedido rechazado (%s) para la cliente %s, pedido %s.",
        error.motivo, cliente.pk, pedido.pk if pedido else None,
    )


def _registrar_historial(*, pedido: Pedido, usuario: Usuario, anterior: str | None) -> None:
    HistorialEstadoPedido.objects.create(
        pedido=pedido, usuario=usuario, estado_anterior=anterior, estado_nuevo=pedido.estado,
    )


def piezas_entregadas() -> int:
    """Suma de las cantidades de las líneas de pedidos Entregados, en una sola consulta."""
    total = DetallePedido.objects.filter(pedido__estado=Estado.ENTREGADO).aggregate(total=Sum("cantidad"))["total"]
    return int(total or 0)


def dias_en_cola() -> int:
    """Días comprometidos en pedidos Confirmados y En preparación (cantidad × dias_produccion)."""
    total = DetallePedido.objects.filter(pedido__estado__in=ESTADOS_EN_COLA).aggregate(
        total=Sum(F("cantidad") * F("dias_produccion")),
    )["total"]
    return int(total or 0)


def _dias_propios(lineas: list[tuple[Producto, int]]) -> int:
    return sum(
        cantidad * producto.tiempo_produccion_dias
        for producto, cantidad in lineas if producto.tipo == Producto.Tipo.SOBRE_PEDIDO
    )


def estimar_fecha_entrega(*, lineas: Iterable[Any], fecha_base: date | None = None) -> date:
    """Motor de fecha (RNF-27): base + cola + días del pedido + DIAS_ALISTAMIENTO, en días calendario."""
    base = fecha_base or timezone.localdate()
    return base + timedelta(days=dias_en_cola() + _dias_propios(_normalizar(lineas)) + DIAS_ALISTAMIENTO)


def desglose_fecha_entrega(*, pedido: Pedido) -> dict[str, Any] | None:
    """Desglose de la fecha guardada de un pedido confirmado; None si aún no se confirmó."""
    if not pedido.fecha_confirmacion or not pedido.fecha_estimada_entrega:
        return None
    base = timezone.localdate(pedido.fecha_confirmacion)
    propios = sum(d.cantidad * (d.dias_produccion or 0) for d in pedido.detalles.all())
    total = (pedido.fecha_estimada_entrega - base).days
    return {
        "fecha_confirmacion": base,
        "dias_cola": total - propios - DIAS_ALISTAMIENTO,
        "dias_propios": propios,
        "dias_alistamiento": DIAS_ALISTAMIENTO,
        "fecha_estimada": pedido.fecha_estimada_entrega,
    }


def _validar_entrega(*, direccion: str, telefono: str) -> tuple[str, str]:
    direccion = (direccion or "").strip()
    telefono = (telefono or "").strip()
    errores = {}
    if not direccion:
        errores["direccion"] = "Ingresa la dirección de entrega."
    if not telefono:
        errores["telefono"] = "Ingresa un teléfono de contacto."
    else:
        try:
            validar_telefono(telefono)
        except ValidationError as error:
            errores["telefono"] = error.messages
    if errores:
        raise ValidationError(errores)
    return direccion, telefono


def crear_pedido(*, cliente: Usuario, lineas: Iterable[Any], direccion: str, telefono: str) -> Pedido:
    """Crea un pedido Pendiente con precios del servidor congelados en cada línea.

    Solo valida la disponibilidad: no reserva ni descuenta. Si falta stock o insumos registra un
    RechazoPedido sin pedido (fuera del bloque revertido) y lanza ValidationError.
    """
    if cliente.rol != Usuario.Rol.CLIENTE:
        raise ValidationError("Solo una Cliente puede crear pedidos.")
    direccion, telefono = _validar_entrega(direccion=direccion, telefono=telefono)
    solicitadas = _normalizar(lineas)
    if not solicitadas:
        raise ValidationError({"bolsa": "Tu bolsa está vacía."})
    actuales = Producto.objects.in_bulk([producto.pk for producto, _ in solicitadas])
    normalizadas = []
    for producto, cantidad in solicitadas:
        actual = actuales.get(producto.pk)
        if actual is None:
            raise ValidationError({"producto": "Uno de los productos ya no está disponible."})
        normalizadas.append((actual, validar_cantidad(producto=actual, cantidad=cantidad, validar_stock=False)))
    try:
        with transaction.atomic():
            _verificar_existencias(normalizadas)
            pedido = Pedido(
                cliente=cliente, estado=Estado.PENDIENTE, direccion_entrega=direccion, telefono_contacto=telefono,
                subtotal=sum((producto.precio * cantidad for producto, cantidad in normalizadas), Decimal("0")),
            )
            pedido.full_clean()
            pedido.save()
            for producto, cantidad in normalizadas:
                detalle = DetallePedido(
                    pedido=pedido, producto=producto, cantidad=cantidad, precio_unitario=producto.precio,
                )
                detalle.full_clean()
                detalle.save()
            _registrar_historial(pedido=pedido, usuario=cliente, anterior=None)
    except _SinExistencias as error:
        _registrar_rechazo(cliente=cliente, pedido=None, error=error)
        raise ValidationError(error.mensaje) from error
    logger.info("Se creó el pedido %s para la cliente %s.", pedido.pk, cliente.pk)
    return pedido


def _bloquear_inventario(producto_ids: Iterable[int]) -> dict[int, Producto]:
    """Bloquea productos y luego sus insumos, siempre en orden de llave primaria."""
    productos = {
        producto.pk: producto
        for producto in Producto.objects.select_for_update().filter(pk__in=list(producto_ids)).order_by("pk")
    }
    insumo_ids = ProductoInsumo.objects.filter(producto_id__in=list(productos)).values_list("insumo_id", flat=True)
    list(Insumo.objects.select_for_update().filter(pk__in=list(insumo_ids)).order_by("pk"))
    return productos


def pagar_y_confirmar(*, pedido: Pedido, simular_exito: bool, usuario: Usuario) -> Pedido:
    """Valida existencias, cobra con la pasarela y, si el pago es exitoso, confirma y descuenta.

    Todo ocurre en una transacción con el pedido bloqueado primero. Un segundo envío sobre un pedido
    ya confirmado lanza PedidoYaConfirmado y no descuenta de nuevo. Si faltan existencias, la
    transacción se revierte, se registra el RechazoPedido con el pedido y este sigue Pendiente.
    """
    try:
        with transaction.atomic():
            bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
            if bloqueado.cliente_id != usuario.pk:
                raise ValidationError("Solo la dueña del pedido puede pagarlo.")
            if bloqueado.estado != Estado.PENDIENTE:
                if bloqueado.estado in ESTADOS_ACEPTADOS:
                    raise PedidoYaConfirmado("Tu pedido ya fue confirmado.")
                raise ValidationError("Este pedido ya no está pendiente de pago.")
            detalles = list(bloqueado.detalles.all())
            productos = _bloquear_inventario(detalle.producto_id for detalle in detalles)
            for detalle in detalles:
                detalle.producto = productos[detalle.producto_id]
            _verificar_existencias(_normalizar(detalles))

            resultado = obtener_pasarela().cobrar(pedido=bloqueado, datos={"simular_exito": simular_exito})
            bloqueado.resultado_pago = resultado
            if not resultado.exitoso:
                bloqueado.pago_simulado_estado = Pedido.PagoSimulado.FALLIDO
                bloqueado.save(update_fields=["pago_simulado_estado"])
                logger.warning("Pago simulado fallido para el pedido %s.", bloqueado.pk)
                return bloqueado

            cola = dias_en_cola()
            for detalle in detalles:
                producto = detalle.producto
                if producto.tipo == Producto.Tipo.DISPONIBLE:
                    actualizados = Producto.objects.filter(
                        pk=producto.pk, stock_producto__gte=detalle.cantidad,
                    ).update(stock_producto=F("stock_producto") - detalle.cantidad)
                    if not actualizados:
                        raise _SinExistencias(
                            RechazoPedido.Motivo.STOCK_INSUFICIENTE,
                            f"No hay unidades suficientes de {producto.nombre}.",
                        )
                    detalle.origen, detalle.dias_produccion = DetallePedido.Origen.STOCK, 0
                else:
                    try:
                        descontar_insumos(pedido=bloqueado, producto=producto, cantidad=detalle.cantidad)
                    except ValidationError as error:
                        raise _SinExistencias(
                            RechazoPedido.Motivo.INSUMOS_INSUFICIENTES,
                            "No hay insumos suficientes para confeccionar tu pedido en este momento.",
                        ) from error
                    detalle.origen = DetallePedido.Origen.CONFECCION
                    detalle.dias_produccion = producto.tiempo_produccion_dias
                detalle.full_clean()
                detalle.save(update_fields=["origen", "dias_produccion"])

            ahora = timezone.now()
            propios = sum(detalle.cantidad * detalle.dias_produccion for detalle in detalles)
            bloqueado.pago_simulado_estado = Pedido.PagoSimulado.EXITOSO
            bloqueado.fecha_confirmacion = ahora
            bloqueado.fecha_estimada_entrega = timezone.localdate(ahora) + timedelta(
                days=cola + propios + DIAS_ALISTAMIENTO,
            )
            bloqueado.estado = Estado.CONFIRMADO
            bloqueado.full_clean()
            bloqueado.save()
            _registrar_historial(pedido=bloqueado, usuario=usuario, anterior=Estado.PENDIENTE)
    except _SinExistencias as error:
        _registrar_rechazo(cliente=usuario, pedido=pedido, error=error)
        raise ValidationError(error.mensaje) from error
    logger.info("Se confirmó el pedido %s con entrega estimada %s.", bloqueado.pk, bloqueado.fecha_estimada_entrega)
    return bloqueado


def cambiar_estado(*, pedido: Pedido, nuevo_estado: str, usuario: Usuario) -> Pedido:
    """Avanza un pedido: Confirmado → En preparación → Listo → Entregado."""
    if usuario.rol != Usuario.Rol.EMPRENDEDORA:
        raise ValidationError("Solo la Emprendedora puede cambiar el estado de un pedido.")
    with transaction.atomic():
        bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
        anterior = bloqueado.estado
        if SIGUIENTE_ESTADO.get(anterior) != nuevo_estado:
            raise ValidationError(
                f"No se puede pasar de «{bloqueado.get_estado_display()}» a «{Estado(nuevo_estado).label}»."
                if nuevo_estado in Estado.values else "Selecciona un estado válido."
            )
        bloqueado.estado = nuevo_estado
        if nuevo_estado == Estado.ENTREGADO:
            bloqueado.fecha_entrega_real = timezone.localdate()
        bloqueado.full_clean()
        bloqueado.save()
        _registrar_historial(pedido=bloqueado, usuario=usuario, anterior=anterior)
    logger.info("El pedido %s pasó de %s a %s.", bloqueado.pk, anterior, nuevo_estado)
    return bloqueado


def cancelar_pedido(*, pedido: Pedido, usuario: Usuario) -> Pedido:
    """Cancela un pedido y, si estaba Confirmado, devuelve exactamente lo descontado.

    La Cliente cancela solo sus pedidos Pendientes; la Emprendedora, Pendientes o Confirmados.
    """
    with transaction.atomic():
        bloqueado = Pedido.objects.select_for_update().get(pk=pedido.pk)
        anterior = bloqueado.estado
        if usuario.rol == Usuario.Rol.CLIENTE:
            if bloqueado.cliente_id != usuario.pk:
                raise ValidationError("Solo puedes cancelar tus propios pedidos.")
            if anterior != Estado.PENDIENTE:
                raise ValidationError("Solo puedes cancelar pedidos que están en espera de pago.")
        elif usuario.rol == Usuario.Rol.EMPRENDEDORA:
            if anterior not in (Estado.PENDIENTE, Estado.CONFIRMADO):
                raise ValidationError("Solo se pueden cancelar pedidos Pendientes o Confirmados.")
        else:
            raise ValidationError("No tienes permiso para cancelar pedidos.")

        if anterior == Estado.CONFIRMADO:
            detalles = list(bloqueado.detalles.all())
            _bloquear_inventario(detalle.producto_id for detalle in detalles)
            for detalle in detalles:
                if detalle.origen == DetallePedido.Origen.STOCK:
                    Producto.objects.filter(pk=detalle.producto_id).update(
                        stock_producto=F("stock_producto") + detalle.cantidad,
                    )
            devolver_insumos(pedido=bloqueado)

        bloqueado.estado = Estado.CANCELADO
        bloqueado.fecha_cancelacion = timezone.now()
        bloqueado.full_clean()
        bloqueado.save()
        _registrar_historial(pedido=bloqueado, usuario=usuario, anterior=anterior)
    logger.info("El pedido %s se canceló desde %s por el usuario %s.", bloqueado.pk, anterior, usuario.pk)
    return bloqueado


ESTADOS_LINEA = [Estado.PENDIENTE, Estado.CONFIRMADO, Estado.EN_PREPARACION, Estado.LISTO, Estado.ENTREGADO]

DESCRIPCIONES_ETAPA = {
    Estado.PENDIENTE: "Esperamos el pago simulado para confirmar tu pedido.",
    Estado.CONFIRMADO: "Recibimos el pago y tu pedido entró a la agenda del taller.",
    Estado.EN_PREPARACION: "La emprendedora está alistando y empacando tu pedido.",
    Estado.LISTO: "Tu pedido está empacado y listo para la entrega.",
    Estado.ENTREGADO: "Entregamos tu pedido en la dirección indicada.",
}
DESCRIPCION_EN_CONFECCION = "Tus piezas se están confeccionando a mano en el taller."


def linea_de_estados(*, pedido: Pedido, para_cliente: bool = True) -> list[dict[str, Any]]:
    """Etapas del pedido con la fecha de cada cambio tomada del historial (requiere historial precargado).

    En_preparacion se llama «En confección» si alguna línea se confecciona y «En preparación» si todo
    sale del stock, para la Cliente y para la Emprendedora (ver `nombre_estado`).
    """
    fechas = {registro.estado_nuevo: registro.fecha_cambio for registro in pedido.historial.all()}
    actual = ESTADOS_LINEA.index(pedido.estado) if pedido.estado in ESTADOS_LINEA else -1
    con_confeccion = pedido.tiene_confeccion
    etapas = []
    for indice, estado in enumerate(ESTADOS_LINEA):
        confeccion_visible = estado == Estado.EN_PREPARACION and con_confeccion
        etapas.append({
            "estado": estado,
            "nombre": nombre_estado(estado, con_confeccion=con_confeccion, para_cliente=para_cliente),
            "descripcion": DESCRIPCION_EN_CONFECCION if confeccion_visible else DESCRIPCIONES_ETAPA[estado],
            "fecha": fechas.get(estado),
            # En un Cancelado se marcan como alcanzadas las etapas que registró el historial.
            "completado": (
                estado in fechas if pedido.estado == Estado.CANCELADO
                else indice < actual or (indice == actual and estado == Estado.ENTREGADO)
            ),
            "actual": indice == actual,
        })
    return etapas


def pedidos_de_cliente(*, cliente: Usuario) -> QuerySet[Pedido]:
    """Pedidos de una Cliente, del más reciente al más antiguo, con sus líneas para nombrar el estado."""
    return Pedido.objects.filter(cliente=cliente).prefetch_related(
        Prefetch("detalles", queryset=DetallePedido.objects.select_related("producto")),
    ).order_by("-id_pedido")


def obtener_pedido_de_cliente(*, cliente: Usuario, pedido_id: int) -> Pedido | None:
    """Pedido de la Cliente con sus líneas e historial; None si no existe o es de otra Cliente."""
    return Pedido.objects.filter(pk=pedido_id, cliente=cliente).prefetch_related(
        Prefetch("detalles", queryset=DetallePedido.objects.select_related("producto")), "historial",
    ).first()


# --- Gestión de la Emprendedora ---

ESTADOS_FILTRO = [
    Estado.PENDIENTE, Estado.CONFIRMADO, Estado.EN_PREPARACION, Estado.LISTO, Estado.ENTREGADO, Estado.CANCELADO,
]
ESTADOS_CANCELABLES_EMPRENDEDORA = [Estado.PENDIENTE, Estado.CONFIRMADO]
PATRON_NUMERO_PEDIDO = re.compile(r"^#?\s*(?:TH\s*-?\s*)?0*(\d{1,9})$", re.IGNORECASE)


def _filtro_busqueda(busqueda: str) -> Q:
    """Busca por número visible (#TH-0012, TH-12 o 12) o por nombre de la clienta, sin distinguir tildes."""
    busqueda = (busqueda or "").strip()
    if not busqueda:
        return Q()
    filtro = Q(cliente__nombre__unaccent__icontains=busqueda)
    numero = PATRON_NUMERO_PEDIDO.match(busqueda)
    if numero:
        filtro |= Q(pk=int(numero.group(1)))
    return filtro


def pedidos_para_gestion(*, estado: str = "", busqueda: str = "") -> QuerySet[Pedido]:
    """Pedidos para la tabla de la Emprendedora, con clienta y líneas precargadas (sin N+1)."""
    pedidos = Pedido.objects.filter(_filtro_busqueda(busqueda)).select_related("cliente").prefetch_related(
        Prefetch("detalles", queryset=DetallePedido.objects.select_related("producto").order_by("id_detalle")),
    ).order_by("-id_pedido")
    if estado in Estado.values:
        pedidos = pedidos.filter(estado=estado)
    return pedidos


def conteos_por_estado(*, busqueda: str = "") -> dict[str, int]:
    """Total y conteo por estado en una sola consulta (Count con filter)."""
    conteos = Pedido.objects.filter(_filtro_busqueda(busqueda)).aggregate(
        todos=Count("id_pedido"),
        **{estado: Count("id_pedido", filter=Q(estado=estado)) for estado in ESTADOS_FILTRO},
    )
    return {clave: valor or 0 for clave, valor in conteos.items()}


def obtener_pedido_para_gestion(*, pedido_id: int) -> Pedido | None:
    """Pedido con clienta, líneas, historial y movimientos de insumos para el panel; None si no existe."""
    return Pedido.objects.filter(pk=pedido_id).select_related("cliente").prefetch_related(
        Prefetch("detalles", queryset=DetallePedido.objects.select_related("producto").order_by("id_detalle")),
        "historial",
        Prefetch("movimientos_insumo", queryset=MovimientoInsumo.objects.select_related("insumo").order_by(
            "fecha_movimiento", "id_movimiento",
        )),
    ).first()


def siguiente_estado(*, pedido: Pedido) -> str | None:
    """Estado al que la Emprendedora puede avanzar el pedido; None si no avanza más."""
    return SIGUIENTE_ESTADO.get(pedido.estado)


def preparar_pedido_desde_bolsa(*, cliente: Usuario, bolsa: Bolsa, direccion: str, telefono: str) -> Pedido:
    """Crea el pedido Pendiente de la bolsa o reutiliza el de la sesión si nada cambió.

    El Pendiente de la sesión solo se reutiliza si es de la misma Cliente y sigue Pendiente; si ya se
    pagó o canceló (por ejemplo, en otra pestaña) se ignora. Si la bolsa o la entrega cambiaron, se
    crea uno nuevo y el anterior se cancela.
    """
    lineas = bolsa.lineas()
    previo = None
    if bolsa.pedido_pendiente_id:
        previo = Pedido.objects.filter(
            pk=bolsa.pedido_pendiente_id, cliente=cliente, estado=Estado.PENDIENTE,
        ).prefetch_related("detalles").first()
    if previo is not None:
        mismas_lineas = (
            {detalle.producto_id: detalle.cantidad for detalle in previo.detalles.all()}
            == {linea.producto.pk: linea.cantidad for linea in lineas}
        )
        misma_entrega = (
            previo.direccion_entrega == (direccion or "").strip()
            and previo.telefono_contacto == (telefono or "").strip()
        )
        if mismas_lineas and misma_entrega:
            logger.info("Se reutilizó el pedido pendiente %s.", previo.pk)
            return previo
    nuevo = crear_pedido(cliente=cliente, lineas=lineas, direccion=direccion, telefono=telefono)
    if previo is not None:
        try:
            cancelar_pedido(pedido=previo, usuario=cliente)
        except ValidationError:
            # Pudo pagarse o cancelarse en otra pestaña justo ahora: se sigue con el pedido nuevo.
            logger.warning("No se pudo cancelar el pedido pendiente %s al reemplazarlo por %s.", previo.pk, nuevo.pk)
        else:
            logger.info("El pedido pendiente %s se reemplazó por %s.", previo.pk, nuevo.pk)
    bolsa.pedido_pendiente_id = nuevo.pk
    return nuevo
