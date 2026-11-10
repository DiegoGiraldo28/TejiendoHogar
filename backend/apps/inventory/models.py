"""Modelos de insumos, recetas y movimientos de inventario."""
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.catalog.models import Producto


class Tipo(models.TextChoices):
    ENTRADA = "Entrada", "Entrada"
    DESCUENTO = "Descuento", "Descuento"
    DEVOLUCION = "Devolucion", "Devolución"


class Insumo(models.Model):
    """Materia prima y cantidad disponible en el taller."""

    class Unidad(models.TextChoices):
        METROS = "metros", "Metros"
        UNIDADES = "unidades", "Unidades"
        CONOS = "conos", "Conos"
        ROLLOS = "rollos", "Rollos"
        GRAMOS = "gramos", "Gramos"

    id_insumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    unidad_medida = models.CharField(max_length=20, choices=Unidad.choices)
    cantidad_disponible = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0, message="La cantidad disponible debe ser igual o mayor que 0.")],
    )
    stock_minimo = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0, message="El stock mínimo debe ser igual o mayor que 0.")],
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "insumo"
        indexes = [models.Index(fields=["cantidad_disponible"], name="idx_insumo_cantidad_disponible")]
        constraints = [
            models.UniqueConstraint(fields=["nombre"], name="uq_insumo_nombre"),
            models.CheckConstraint(
                condition=models.Q(cantidad_disponible__gte=0), name="ck_insumo_cantidad",
                violation_error_message="La cantidad disponible debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=models.Q(stock_minimo__gte=0), name="ck_insumo_stock_minimo",
                violation_error_message="El stock mínimo debe ser igual o mayor que 0.",
            ),
        ]

    def clean(self):
        super().clean()
        self.nombre = (self.nombre or "").strip()
        if not self.nombre:
            raise ValidationError({"nombre": "El nombre del insumo es obligatorio."})

    @property
    def en_stock_bajo(self):
        """Indica si la cantidad disponible llegó al mínimo configurado."""
        return self.cantidad_disponible <= self.stock_minimo

    def __str__(self):
        return self.nombre


class ProductoInsumo(models.Model):
    """Línea de receta: cantidad de un insumo para una unidad de producto."""
    id_producto_insumo = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Producto, db_column="id_producto", on_delete=models.CASCADE, related_name="receta")
    insumo = models.ForeignKey(Insumo, db_column="id_insumo", on_delete=models.PROTECT)
    cantidad_requerida = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0.01, message="La cantidad requerida debe ser mayor que 0.")],
    )

    class Meta:
        db_table = "producto_insumo"
        indexes = [
            models.Index(fields=["producto"], name="idx_prodinsumo_producto"),
            models.Index(fields=["insumo"], name="idx_prodinsumo_insumo"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["producto", "insumo"], name="uq_producto_insumo"),
            models.CheckConstraint(
                condition=models.Q(cantidad_requerida__gt=0), name="ck_prodinsumo_cantidad",
                violation_error_message="La cantidad requerida debe ser mayor que 0.",
            ),
        ]


class MovimientoInsumo(models.Model):
    """Registro de entradas y futuros descuentos o devoluciones."""

    Tipo = Tipo

    id_movimiento = models.AutoField(primary_key=True)
    insumo = models.ForeignKey(Insumo, db_column="id_insumo", on_delete=models.PROTECT)
    # TODO Fase 3: agregar id_pedido y sus restricciones al integrar pedidos.
    tipo_movimiento = models.CharField(max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(
        0.01, message="La cantidad del movimiento debe ser mayor que 0.")])
    fecha_movimiento = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "movimiento_insumo"
        indexes = [
            models.Index(fields=["insumo"], name="idx_movimiento_insumo"),
            models.Index(fields=["tipo_movimiento"], name="idx_movimiento_tipo"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tipo_movimiento__in=Tipo.values), name="ck_movimiento_tipo",
                violation_error_message="Selecciona un tipo de movimiento válido.",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0), name="ck_movimiento_cantidad",
                violation_error_message="La cantidad del movimiento debe ser mayor que 0.",
            ),
        ]

    def __str__(self):
        return f"{self.tipo_movimiento} · {self.insumo} · {self.cantidad}"
