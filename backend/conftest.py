"""Fixtures compartidas entre las apps del proyecto."""
import pytest
import struct
import zlib
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

Usuario = get_user_model()


@pytest.fixture(autouse=True)
def media_temporal(tmp_path, settings):
    """Guarda archivos subidos por pruebas en el directorio temporal del caso."""
    settings.MEDIA_ROOT = tmp_path


def crear_png_prueba(ancho=200, alto=200):
    """Crea un PNG RGBA válido sin Pillow y con dimensiones configurables."""
    def bloque(tipo, contenido):
        return (struct.pack(">I", len(contenido)) + tipo + contenido
                + struct.pack(">I", zlib.crc32(tipo + contenido) & 0xFFFFFFFF))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    filas = b"".join(b"\x00" + bytes(ancho * 4) for _ in range(alto))
    return (b"\x89PNG\r\n\x1a\n" + bloque(b"IHDR", cabecera)
            + bloque(b"IDAT", zlib.compress(filas)) + bloque(b"IEND", b""))


def imagen_png_prueba(nombre="prueba.png", contenido=None, ancho=200, alto=200):
    """Devuelve un archivo subido válido para las pruebas de producto."""
    contenido = contenido if contenido is not None else crear_png_prueba(ancho, alto)
    return SimpleUploadedFile(nombre, contenido, content_type="image/png")


def imagen_cabecera_prueba(formato, ancho=200, alto=200, variante=""):
    """Crea una cabecera de imagen de prueba para validar dimensiones por formato."""
    if formato == "png":
        return imagen_png_prueba(f"prueba.png", ancho=ancho, alto=alto)
    if formato == "jpg":
        marcador = 0xC2 if variante == "sof2" else 0xC0
        segmento = (b"\xff\xd8\xff" + bytes([marcador]) + struct.pack(">H", 11)
                    + bytes([8]) + struct.pack(">HHB", alto, ancho, 1) + b"\x01\x11\x00\xff\xd9")
        return SimpleUploadedFile("prueba.jpg", segmento, content_type="image/jpeg")
    if formato != "webp":
        raise ValueError("Formato de prueba no soportado.")
    if variante == "vp8l":
        ancho_menos_uno, alto_menos_uno = ancho - 1, alto - 1
        datos = bytes([0x2F, ancho_menos_uno & 0xFF,
                       ((ancho_menos_uno >> 8) & 0x3F) | ((alto_menos_uno & 0x03) << 6),
                       (alto_menos_uno >> 2) & 0xFF, (alto_menos_uno >> 10) & 0x0F])
        tipo = b"VP8L"
    elif variante == "vp8":
        datos = (b"\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", ancho & 0x3FFF, alto & 0x3FFF))
        tipo = b"VP8 "
    else:
        datos = (b"\x00\x00\x00\x00" + (ancho - 1).to_bytes(3, "little")
                 + (alto - 1).to_bytes(3, "little"))
        tipo = b"VP8X"
    chunk = tipo + struct.pack("<I", len(datos)) + datos
    contenido = b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk
    return SimpleUploadedFile("prueba.webp", contenido, content_type="image/webp")


def crear_producto_prueba(*, nombre="Producto de prueba", descripcion="Hecha a mano", precio="45000",
                          imagen=None, tipo="Disponible", tiempo_produccion_dias=5, stock_producto=4,
                          stock_minimo=1, activo=None):
    """Crea productos con los valores válidos que comparten las pruebas de catálogo e inventario."""
    from apps.catalog.models import Producto
    from apps.catalog.services import crear_producto

    producto = crear_producto(
        nombre=nombre, descripcion=descripcion, precio=precio,
        imagen=imagen or imagen_png_prueba(), tipo=tipo,
        tiempo_produccion_dias=tiempo_produccion_dias,
        stock_producto=stock_producto, stock_minimo=stock_minimo,
    )
    if activo is not None and producto.activo != activo:
        producto.activo = activo
        producto.save(update_fields=["activo"])
    return producto


@pytest.fixture
def cliente(db):
    return Usuario.objects.create_user("ana@example.com", "ClaveFuerte-2026", nombre="Ana")


@pytest.fixture
def emprendedora(db):
    return Usuario.objects.create_superuser("taller@example.com", "ClaveFuerte-2026", nombre="Taller")
