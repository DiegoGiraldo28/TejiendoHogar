"""Reglas de negocio del catálogo."""
import logging

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404

from .models import Producto

logger = logging.getLogger(__name__)


def crear_producto(*, nombre, descripcion, precio, imagen, tipo, tiempo_produccion_dias, stock_producto=0, stock_minimo=0):
    """Valida y crea un producto. Devuelve Producto o lanza ValidationError."""
    activo = tipo == Producto.Tipo.DISPONIBLE
    producto = Producto(
        nombre=nombre, descripcion=descripcion, precio=precio, imagen=imagen, tipo=tipo,
        tiempo_produccion_dias=tiempo_produccion_dias,
        stock_producto=stock_producto if activo else 0, stock_minimo=stock_minimo, activo=activo,
    )
    try:
        producto.full_clean()
        producto.save()
    except ValidationError:
        logger.exception("No se pudo crear un producto por datos inválidos.")
        raise
    logger.info("Se creó el producto %s (%s).", producto.id_producto, producto.nombre)
    return producto


def actualizar_producto(*, producto, nombre, descripcion, precio, tipo, tiempo_produccion_dias, stock_producto=0, stock_minimo=0, imagen=None):
    """Actualiza los campos del producto y elimina la imagen reemplazada."""
    imagen_anterior = producto.imagen.name
    producto.nombre = nombre
    producto.descripcion = descripcion
    producto.precio = precio
    producto.tipo = tipo
    producto.tiempo_produccion_dias = tiempo_produccion_dias
    producto.stock_producto = stock_producto if tipo == Producto.Tipo.DISPONIBLE else 0
    producto.stock_minimo = stock_minimo
    if imagen:
        producto.imagen = imagen
    if tipo == Producto.Tipo.SOBRE_PEDIDO and not producto.receta.exists():
        producto.activo = False
    producto.full_clean()
    producto.save()
    if imagen and imagen_anterior and imagen_anterior != producto.imagen.name:
        producto.imagen.storage.delete(imagen_anterior)
    logger.info("Se actualizó el producto %s.", producto.id_producto)
    return producto


def cambiar_estado(*, producto):
    """Activa o desactiva el producto; un encargo activo requiere receta."""
    if not producto.activo and producto.tipo == Producto.Tipo.SOBRE_PEDIDO and not producto.receta.exists():
        logger.warning("Se rechazó activar el producto %s sin receta.", producto.id_producto)
        raise ValidationError({"activo": "Agrega al menos un insumo a la receta antes de activar este producto."})
    producto.activo = not producto.activo
    producto.full_clean()
    producto.save(update_fields=["activo", "fecha_actualizacion"])
    logger.info("Se cambió el estado del producto %s a %s.", producto.id_producto, producto.activo)
    return producto


def eliminar_producto(*, producto):
    """Elimina el producto o informa si otros datos lo protegen."""
    nombre_imagen = producto.imagen.name
    try:
        producto.delete()
    except ProtectedError as error:
        logger.warning("No se pudo eliminar el producto %s porque tiene relaciones protegidas.", producto.id_producto)
        raise ValidationError({"producto": "Este producto tiene pedidos asociados; desactívalo en lugar de eliminarlo."}) from error
    if nombre_imagen:
        producto.imagen.storage.delete(nombre_imagen)
    logger.info("Se eliminó el producto %s.", producto.id_producto)


def listar_admin(*, busqueda="", estado="", tipo=""):
    """Devuelve productos de gestión con estado de receta en una consulta."""
    productos = Producto.objects.annotate(receta_count=Count("receta", distinct=True)).order_by("nombre")
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda.strip())
    if estado in ("activo", "inactivo"):
        productos = productos.filter(activo=(estado == "activo"))
    if tipo in Producto.Tipo.values:
        productos = productos.filter(tipo=tipo)
    return productos


def listar_publicos(*, busqueda="", tipo=None):
    """Devuelve un paginador de productos activos con filtros simples."""
    productos = Producto.objects.filter(activo=True).only(
        "id_producto", "nombre", "precio", "imagen", "tipo", "tiempo_produccion_dias", "stock_producto"
    ).order_by("nombre")
    if busqueda:
        productos = productos.filter(nombre__icontains=busqueda.strip())
    if tipo in Producto.Tipo.values:
        productos = productos.filter(tipo=tipo)
    return Paginator(productos, 12)


def productos_destacados(*, limite=4):
    """Devuelve los productos activos más recientes para mostrar en la bienvenida."""
    return Producto.objects.filter(activo=True).only(
        "id_producto", "nombre", "precio", "imagen", "tipo", "tiempo_produccion_dias", "stock_producto"
    ).order_by("-fecha_creacion")[:limite]


def obtener_publico(*, id_producto):
    """Devuelve un producto activo o lanza Http404 si no es visible."""
    try:
        return Producto.objects.get(id_producto=id_producto, activo=True)
    except Producto.DoesNotExist as error:
        raise Http404("Producto no encontrado") from error
