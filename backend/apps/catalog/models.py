"""Modelo de productos según el esquema de TejiendoHogar."""
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Trim
from django.db.models.lookups import Exact


LIMITE_IMAGEN_BYTES = 2 * 1024 * 1024


def validar_tamano_imagen(archivo):
    """Rechaza imágenes mayores de dos megabytes."""
    if archivo.size > LIMITE_IMAGEN_BYTES:
        raise ValidationError("La imagen no puede superar los 2 MB.")


class Producto(models.Model):
    """Prenda disponible para compra o confección por encargo."""

    class Tipo(models.TextChoices):
        DISPONIBLE = "Disponible", "Disponible"
        SOBRE_PEDIDO = "Sobre_pedido", "Sobre pedido"

    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    imagen = models.FileField(
        upload_to="productos/", max_length=255, db_column="imagen_url",
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"], message="Usa una imagen JPG, PNG o WEBP."), validar_tamano_imagen],
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    tiempo_produccion_dias = models.PositiveIntegerField()
    stock_producto = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "producto"
        indexes = [
            models.Index(fields=["activo"], name="idx_producto_activo"),
            models.Index(fields=["tipo"], name="idx_producto_tipo"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(tipo__in=["Disponible", "Sobre_pedido"]), name="ck_producto_tipo"),
            models.CheckConstraint(condition=Q(precio__gte=0), name="ck_producto_precio"),
            models.CheckConstraint(condition=Q(tiempo_produccion_dias__gt=0), name="ck_producto_tiempo_produccion"),
            models.CheckConstraint(condition=Q(stock_producto__gte=0), name="ck_producto_stock"),
            models.CheckConstraint(condition=Q(stock_minimo__gte=0), name="ck_producto_stock_minimo"),
            models.CheckConstraint(condition=~Exact(Trim("descripcion"), Value("")), name="ck_producto_descripcion"),
            models.CheckConstraint(condition=~Exact(Trim("imagen"), Value("")), name="ck_producto_imagen"),
        ]

    def clean(self):
        super().clean()
        self.nombre = (self.nombre or "").strip()
        self.descripcion = (self.descripcion or "").strip()
        if not self.descripcion:
            raise ValidationError({"descripcion": "La descripción es obligatoria."})
        if self.imagen and not getattr(self.imagen, "_committed", False):
            self._validar_firma_imagen()

    def _validar_firma_imagen(self):
        """Verifica que los bytes coincidan con la extensión permitida."""
        nombre = self.imagen.name.lower()
        self.imagen.seek(0)
        firma = self.imagen.read(12)
        self.imagen.seek(0)
        valida = (
            (nombre.endswith((".jpg", ".jpeg")) and firma.startswith(b"\xff\xd8\xff"))
            or (nombre.endswith(".png") and firma.startswith(b"\x89PNG\r\n\x1a\n"))
            or (nombre.endswith(".webp") and firma[:4] == b"RIFF" and firma[8:12] == b"WEBP")
        )
        if not valida:
            raise ValidationError({"imagen": "El contenido del archivo no coincide con una imagen JPG, PNG o WEBP válida."})

    @property
    def en_stock_bajo(self):
        """Indica si un producto Disponible alcanzó su stock mínimo."""
        return self.tipo == self.Tipo.DISPONIBLE and self.stock_producto <= self.stock_minimo

    def __str__(self):
        return self.nombre
