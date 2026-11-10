"""Modelo de productos según el esquema de TejiendoHogar."""
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Value
from django.db.models.functions import Trim
from django.db.models.lookups import Exact
from apps.common.constants import LIMITE_IMAGEN_BYTES, MINIMO_IMAGEN_PIXELES


class Tipo(models.TextChoices):
    DISPONIBLE = "Disponible", "Disponible"
    SOBRE_PEDIDO = "Sobre_pedido", "Sobre pedido"


PRECIO_MINIMO = 0


def validar_tamano_imagen(archivo):
    """Rechaza archivos de más de 2 MB."""
    if archivo.size > LIMITE_IMAGEN_BYTES:
        raise ValidationError("La imagen no puede superar los 2 MB.")


def _dimensiones_imagen(datos):
    """Lee las dimensiones PNG, JPEG o WEBP desde sus cabeceras."""
    if datos.startswith(b"\x89PNG\r\n\x1a\n") and len(datos) >= 24:
        return int.from_bytes(datos[16:20], "big"), int.from_bytes(datos[20:24], "big")
    if datos.startswith(b"RIFF") and datos[8:12] == b"WEBP" and len(datos) >= 20:
        tipo = datos[12:16]
        if tipo == b"VP8X" and len(datos) >= 30:
            ancho = 1 + int.from_bytes(datos[24:27], "little")
            alto = 1 + int.from_bytes(datos[27:30], "little")
            return ancho, alto
        if tipo == b"VP8 " and len(datos) >= 30 and datos[23:26] == b"\x9d\x01\x2a":
            return (int.from_bytes(datos[26:28], "little") & 0x3fff,
                    int.from_bytes(datos[28:30], "little") & 0x3fff)
        if tipo == b"VP8L" and len(datos) >= 25 and datos[20] == 0x2f:
            b0, b1, b2, b3 = datos[21:25]
            return 1 + ((b1 & 0x3f) << 8) + b0, 1 + ((b3 & 0x0f) << 10) + (b2 << 2) + (b1 >> 6)
        return None
    if not datos.startswith(b"\xff\xd8\xff"):
        return None
    indice = 2
    while indice + 4 <= len(datos):
        if datos[indice] != 0xff:
            indice += 1
            continue
        while indice < len(datos) and datos[indice] == 0xff:
            indice += 1
        if indice >= len(datos):
            break
        marcador = datos[indice]
        indice += 1
        if marcador in (0xd8, 0xd9, 0x01) or 0xd0 <= marcador <= 0xd7:
            continue
        if indice + 2 > len(datos):
            break
        longitud = int.from_bytes(datos[indice:indice + 2], "big")
        if marcador in (0xc0, 0xc2):
            if longitud < 7 or indice + 7 > len(datos):
                break
            alto = int.from_bytes(datos[indice + 3:indice + 5], "big")
            ancho = int.from_bytes(datos[indice + 5:indice + 7], "big")
            return ancho, alto
        indice += longitud
    return None


class Producto(models.Model):
    """Prenda disponible para compra o confección por encargo."""

    Tipo = Tipo

    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(
        PRECIO_MINIMO, message="El precio debe ser igual o mayor que 0.")])
    imagen = models.FileField(
        upload_to="productos/", max_length=255, db_column="imagen_url",
        validators=[
            FileExtensionValidator(
                ["jpg", "jpeg", "png", "webp"], message="Usa una imagen JPG, PNG o WEBP.",
            ),
            validar_tamano_imagen,
        ],
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    tiempo_produccion_dias = models.PositiveIntegerField(validators=[MinValueValidator(
        1, message="Los días de producción deben ser al menos 1.")])
    stock_producto = models.PositiveIntegerField(default=0, validators=[MinValueValidator(
        0, message="El stock debe ser igual o mayor que 0.")])
    stock_minimo = models.PositiveIntegerField(default=0, validators=[MinValueValidator(
        0, message="El stock mínimo debe ser igual o mayor que 0.")])
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
            models.CheckConstraint(
                condition=Q(tipo__in=Tipo.values), name="ck_producto_tipo",
                violation_error_message="Selecciona un tipo de producto válido.",
            ),
            models.CheckConstraint(
                condition=Q(precio__gte=PRECIO_MINIMO), name="ck_producto_precio",
                violation_error_message="El precio debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=Q(tiempo_produccion_dias__gt=0), name="ck_producto_tiempo_produccion",
                violation_error_message="Los días de producción deben ser al menos 1.",
            ),
            models.CheckConstraint(
                condition=Q(stock_producto__gte=0), name="ck_producto_stock",
                violation_error_message="El stock debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=Q(stock_minimo__gte=0), name="ck_producto_stock_minimo",
                violation_error_message="El stock mínimo debe ser igual o mayor que 0.",
            ),
            models.CheckConstraint(
                condition=~Exact(Trim("descripcion"), Value("")), name="ck_producto_descripcion",
                violation_error_message="La descripción es obligatoria.",
            ),
            models.CheckConstraint(
                condition=~Exact(Trim("imagen"), Value("")), name="ck_producto_imagen",
                violation_error_message="La imagen es obligatoria.",
            ),
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
        datos = self.imagen.read()
        firma = datos[:12]
        self.imagen.seek(0)
        valida = (
            (nombre.endswith((".jpg", ".jpeg")) and firma.startswith(b"\xff\xd8\xff"))
            or (nombre.endswith(".png") and firma.startswith(b"\x89PNG\r\n\x1a\n"))
            or (nombre.endswith(".webp") and firma[:4] == b"RIFF" and firma[8:12] == b"WEBP")
        )
        if not valida:
            raise ValidationError({
                "imagen": "El contenido del archivo no coincide con una imagen JPG, PNG o WEBP válida.",
            })
        dimensiones = _dimensiones_imagen(datos)
        if not dimensiones or min(dimensiones) < MINIMO_IMAGEN_PIXELES:
            raise ValidationError({"imagen": "La imagen debe medir al menos 200 × 200 píxeles."})

    @property
    def en_stock_bajo(self):
        """Indica si un producto Disponible alcanzó su stock mínimo."""
        return self.tipo == self.Tipo.DISPONIBLE and self.stock_producto <= self.stock_minimo

    def __str__(self):
        return self.nombre
