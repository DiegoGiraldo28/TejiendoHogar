"""Modelos de pedidos según docs/tejiendohogar_schema1.sql."""
from django.conf import settings
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Trim
from django.db.models.lookups import Exact

from apps.catalog.models import Producto
from apps.common.validators import PATRON_TELEFONO


class Estado(models.TextChoices):
    PENDIENTE = "Pendiente", "Pendiente"
    CONFIRMADO = "Confirmado", "Confirmado"
    EN_PREPARACION = "En_preparacion", "En preparación"
    LISTO = "Listo", "Listo"
    ENTREGADO = "Entregado", "Entregado"
    CANCELADO = "Cancelado", "Cancelado"


class PagoSimulado(models.TextChoices):
    EXITOSO = "Exitoso", "Exitoso"
    FALLIDO = "Fallido", "Fallido"


class Origen(models.TextChoices):
    STOCK = "Stock", "Stock"
    CONFECCION = "Confeccion", "Confección"


class Motivo(models.TextChoices):
    INSUMOS_INSUFICIENTES = "Insumos_insuficientes", "Insumos insuficientes"
    STOCK_INSUFICIENTE = "Stock_insuficiente", "Stock insuficiente"


ESTADOS_ACEPTADOS = [Estado.CONFIRMADO, Estado.EN_PREPARACION, Estado.LISTO, Estado.ENTREGADO]

NOMBRES_ESTADO_CLIENTE = {
    Estado.PENDIENTE: "En espera de pago",
    Estado.CONFIRMADO: "Confirmado",
    Estado.EN_PREPARACION: "En confección",
    Estado.LISTO: "Listo y empaque",
    Estado.ENTREGADO: "Entregado",
    Estado.CANCELADO: "Cancelado",
}


class Pedido(models.Model):
    """Pedido de una Cliente; no se elimina, se cancela."""

    Estado = Estado
    PagoSimulado = PagoSimulado

    id_pedido = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column="id_cliente", on_delete=models.PROTECT, related_name="pedidos",
    )
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    direccion_entrega = models.CharField(max_length=255)
    telefono_contacto = models.CharField(max_length=20)
    pago_simulado_estado = models.CharField(max_length=20, choices=PagoSimulado.choices, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    fecha_estimada_entrega = models.DateField(null=True, blank=True)
    fecha_entrega_real = models.DateField(null=True, blank=True)
    fecha_cancelacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pedido"
        ordering = ["-id_pedido"]
        indexes = [
            models.Index(fields=["cliente"], name="idx_pedido_cliente"),
            models.Index(fields=["estado"], name="idx_pedido_estado"),
            models.Index(fields=["fecha_estimada_entrega"], name="idx_pedido_fecha_estimada"),
            models.Index(fields=["estado", "fecha_confirmacion"], name="idx_pedido_estado_confirmacion"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado__in=Estado.values), name="ck_pedido_estado",
                violation_error_message="Selecciona un estado de pedido válido.",
            ),
            models.CheckConstraint(
                condition=Q(pago_simulado_estado__isnull=True) | Q(pago_simulado_estado__in=PagoSimulado.values),
                name="ck_pedido_pago_estado",
                violation_error_message="El estado del pago simulado no es válido.",
            ),
            models.CheckConstraint(
                condition=Q(subtotal__gte=0), name="ck_pedido_subtotal",
                violation_error_message="El subtotal debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=~Exact(Trim("direccion_entrega"), Value("")), name="ck_pedido_direccion",
                violation_error_message="La dirección de entrega es obligatoria.",
            ),
            models.CheckConstraint(
                condition=Q(telefono_contacto__regex=f"^{PATRON_TELEFONO}$"), name="ck_pedido_telefono",
                violation_error_message="Ingresa un teléfono de contacto válido.",
            ),
            models.CheckConstraint(
                condition=~Q(estado__in=ESTADOS_ACEPTADOS)
                | Q(pago_simulado_estado__isnull=False, pago_simulado_estado=PagoSimulado.EXITOSO),
                name="ck_pedido_pago_exitoso",
                violation_error_message="Solo un pago exitoso permite confirmar el pedido.",
            ),
            models.CheckConstraint(
                condition=~Q(estado__in=ESTADOS_ACEPTADOS)
                | Q(fecha_confirmacion__isnull=False, fecha_estimada_entrega__isnull=False),
                name="ck_pedido_confirmado_datos",
                violation_error_message="Un pedido confirmado necesita fecha de confirmación y fecha estimada.",
            ),
            models.CheckConstraint(
                condition=Q(estado=Estado.CANCELADO, fecha_cancelacion__isnull=False)
                | (~Q(estado=Estado.CANCELADO) & Q(fecha_cancelacion__isnull=True)),
                name="ck_pedido_cancelacion",
                violation_error_message="Solo un pedido cancelado tiene fecha de cancelación, y siempre la tiene.",
            ),
            models.CheckConstraint(
                condition=Q(estado=Estado.ENTREGADO, fecha_entrega_real__isnull=False)
                | (~Q(estado=Estado.ENTREGADO) & Q(fecha_entrega_real__isnull=True)),
                name="ck_pedido_entrega",
                violation_error_message="Solo un pedido entregado tiene fecha de entrega real, y siempre la tiene.",
            ),
        ]

    @property
    def numero_visible(self) -> str:
        """Número de presentación, por ejemplo #TH-0012 (no se guarda)."""
        return f"#TH-{self.id_pedido:04d}"

    @property
    def estado_cliente(self) -> str:
        """Nombre del estado que ve la Cliente en el seguimiento."""
        return NOMBRES_ESTADO_CLIENTE[self.estado]

    @property
    def estado_emprendedora(self) -> str:
        """Nombre del estado que ve la Emprendedora."""
        return self.get_estado_display()

    def __str__(self):
        return self.numero_visible


class DetallePedido(models.Model):
    """Línea de pedido con el precio congelado al crearlo."""

    Origen = Origen

    id_detalle = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, db_column="id_pedido", on_delete=models.PROTECT, related_name="detalles")
    producto = models.ForeignKey(Producto, db_column="id_producto", on_delete=models.PROTECT)
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    origen = models.CharField(max_length=10, choices=Origen.choices, null=True, blank=True)
    dias_produccion = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "detalle_pedido"
        ordering = ["id_detalle"]
        indexes = [
            models.Index(fields=["pedido"], name="idx_detalle_pedido"),
            models.Index(fields=["producto"], name="idx_detalle_producto"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["pedido", "producto"], name="uq_detalle_pedido_producto",
                violation_error_message="El producto ya está en este pedido.",
            ),
            models.CheckConstraint(
                condition=Q(cantidad__gt=0), name="ck_detalle_cantidad",
                violation_error_message="La cantidad debe ser mayor que 0.",
            ),
            models.CheckConstraint(
                condition=Q(precio_unitario__gte=0), name="ck_detalle_precio",
                violation_error_message="El precio unitario debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=Q(origen__isnull=True) | Q(origen__in=Origen.values), name="ck_detalle_origen",
                violation_error_message="El origen de la línea no es válido.",
            ),
            models.CheckConstraint(
                condition=Q(dias_produccion__isnull=True) | Q(dias_produccion__gte=0), name="ck_detalle_dias",
                violation_error_message="Los días de producción deben ser iguales o mayores que 0.",
            ),
            models.CheckConstraint(
                condition=Q(origen__isnull=True, dias_produccion__isnull=True)
                | Q(origen__isnull=False, dias_produccion__isnull=False),
                name="ck_detalle_origen_dias",
                violation_error_message="El origen y los días de producción se fijan juntos al confirmar.",
            ),
        ]

    @property
    def subtotal(self):
        """Cantidad por precio congelado."""
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.producto} × {self.cantidad}"


class HistorialEstadoPedido(models.Model):
    """Registro inmutable de cada cambio de estado (RNF-09)."""

    id_historial = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, db_column="id_pedido", on_delete=models.PROTECT, related_name="historial")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, db_column="id_usuario", on_delete=models.PROTECT)
    estado_anterior = models.CharField(max_length=20, choices=Estado.choices, null=True, blank=True)
    estado_nuevo = models.CharField(max_length=20, choices=Estado.choices)
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_estado_pedido"
        ordering = ["fecha_cambio", "id_historial"]
        indexes = [models.Index(fields=["pedido"], name="idx_historial_pedido")]
        constraints = [
            models.CheckConstraint(
                condition=Q(estado_anterior__isnull=True) | Q(estado_anterior__in=Estado.values),
                name="ck_historial_estado_anterior",
                violation_error_message="El estado anterior no es válido.",
            ),
            models.CheckConstraint(
                condition=Q(estado_nuevo__in=Estado.values), name="ck_historial_estado_nuevo",
                violation_error_message="El estado nuevo no es válido.",
            ),
        ]


class RechazoPedido(models.Model):
    """Intento de pedido rechazado por falta de existencias."""

    Motivo = Motivo

    id_rechazo = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, db_column="id_cliente", on_delete=models.PROTECT, related_name="rechazos",
    )
    pedido = models.ForeignKey(
        Pedido, db_column="id_pedido", on_delete=models.PROTECT, null=True, blank=True, related_name="rechazos",
    )
    motivo = models.CharField(max_length=30, choices=Motivo.choices)
    fecha_rechazo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rechazo_pedido"
        indexes = [
            models.Index(fields=["motivo"], name="idx_rechazo_motivo"),
            models.Index(fields=["fecha_rechazo"], name="idx_rechazo_fecha"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(motivo__in=Motivo.values), name="ck_rechazo_motivo",
                violation_error_message="El motivo del rechazo no es válido.",
            ),
        ]
