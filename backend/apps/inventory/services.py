"""Operaciones transaccionales y cálculos de inventario."""
import logging
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.deletion import ProtectedError

from apps.catalog.models import Producto
from .models import Insumo, MovimientoInsumo, ProductoInsumo

logger = logging.getLogger(__name__)


def _cantidad_decimal(valor, campo="cantidad"):
    """Convierte una cantidad positiva a Decimal para guardarla con precisión."""
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError({campo: "Ingresa una cantidad válida."}) from error
    if not cantidad.is_finite() or cantidad <= 0:
        raise ValidationError({campo: "La cantidad debe ser mayor que cero."})
    return cantidad


def crear_insumo(*, nombre, unidad_medida, cantidad_disponible=0, stock_minimo=0):
    """Crea un insumo y registra su cantidad inicial como Entrada.

    Devuelve Insumo; lanza ValidationError por duplicados o datos inválidos.
    """
    nombre = nombre.strip()
    if Insumo.objects.filter(nombre__iexact=nombre).exists():
        logger.warning("Se rechazó crear un insumo con nombre repetido.")
        raise ValidationError({"nombre": "Ya existe un insumo con ese nombre."})
    insumo = Insumo(
        nombre=nombre, unidad_medida=unidad_medida,
        cantidad_disponible=cantidad_disponible, stock_minimo=stock_minimo,
    )
    try:
        with transaction.atomic():
            insumo.full_clean()
            insumo.save()
            if insumo.cantidad_disponible > 0:
                movimiento = MovimientoInsumo(
                    insumo=insumo, tipo_movimiento=MovimientoInsumo.Tipo.ENTRADA,
                    cantidad=insumo.cantidad_disponible,
                )
                movimiento.full_clean()
                movimiento.save()
    except IntegrityError as error:
        logger.exception("No se pudo crear el insumo %s.", nombre)
        raise ValidationError({"nombre": "Ya existe un insumo con ese nombre."}) from error
    logger.info("Se creó el insumo %s.", insumo.id_insumo)
    return insumo


def registrar_entrada(*, insumo_id, cantidad):
    """Suma una entrada bajo bloqueo y registra el movimiento atómicamente.

    Recibe ID y cantidad positiva; devuelve MovimientoInsumo o lanza ValidationError.
    """
    cantidad = _cantidad_decimal(cantidad)
    try:
        with transaction.atomic():
            insumo = Insumo.objects.select_for_update().get(pk=insumo_id)
            Insumo.objects.filter(pk=insumo.pk).update(cantidad_disponible=F("cantidad_disponible") + cantidad)
            insumo.refresh_from_db(fields=["cantidad_disponible"])
            movimiento = MovimientoInsumo(
                insumo=insumo, tipo_movimiento=MovimientoInsumo.Tipo.ENTRADA, cantidad=cantidad,
            )
            movimiento.full_clean()
            movimiento.save()
    except Insumo.DoesNotExist as error:
        raise ValidationError({"insumo": "No se encontró el insumo seleccionado."}) from error
    except IntegrityError as error:
        logger.exception("Falló el registro de entrada para el insumo %s.", insumo_id)
        raise ValidationError({"cantidad": "No se pudo registrar la entrada."}) from error
    logger.info("Se registró una entrada para el insumo %s.", insumo_id)
    return movimiento


def actualizar_insumo(*, insumo, nombre, unidad_medida, stock_minimo):
    """Actualiza datos descriptivos sin cambiar existencias."""
    nombre = nombre.strip()
    if Insumo.objects.filter(nombre__iexact=nombre).exclude(pk=insumo.pk).exists():
        logger.warning("Se rechazó renombrar el insumo %s a un nombre repetido.", insumo.pk)
        raise ValidationError({"nombre": "Ya existe un insumo con ese nombre."})
    insumo.nombre = nombre
    insumo.unidad_medida = unidad_medida
    insumo.stock_minimo = stock_minimo
    insumo.full_clean()
    insumo.save(update_fields=["nombre", "unidad_medida", "stock_minimo", "fecha_actualizacion"])
    logger.info("Se actualizó el insumo %s.", insumo.id_insumo)
    return insumo


def eliminar_insumo(*, insumo):
    """Elimina un insumo sin receta ni movimientos previos."""
    if ProductoInsumo.objects.filter(insumo=insumo).exists() or MovimientoInsumo.objects.filter(insumo=insumo).exists():
        logger.warning("Se rechazó eliminar el insumo %s porque está en uso.", insumo.pk)
        raise ValidationError({"insumo": "Este insumo está en uso y no puede eliminarse."})
    try:
        insumo.delete()
    except ProtectedError as error:
        logger.warning("Se protegió el insumo %s durante la eliminación.", insumo.pk)
        raise ValidationError({"insumo": "Este insumo está en uso y no puede eliminarse."}) from error
    logger.info("Se eliminó el insumo %s.", insumo.pk)


def guardar_receta(*, producto, lineas):
    """Reemplaza una receta completa dentro de una transacción.

    Recibe filas con `insumo` y `cantidad_requerida`; devuelve las líneas guardadas
    o lanza ValidationError si hay cantidades inválidas o insumos repetidos.
    """
    normalizadas = []
    ids_insumos = set()
    for linea in lineas:
        if linea.get("DELETE"):
            continue
        insumo = linea.get("insumo")
        cantidad = linea.get("cantidad_requerida")
        if not insumo or cantidad in (None, ""):
            continue
        if insumo.pk in ids_insumos:
            logger.warning("Se rechazó una receta repetida para el producto %s.", producto.pk)
            raise ValidationError({"insumo": "No repitas el mismo insumo en la receta."})
        ids_insumos.add(insumo.pk)
        try:
            cantidad = Decimal(str(cantidad))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValidationError({"cantidad_requerida": "Ingresa una cantidad válida."}) from error
        if not cantidad.is_finite() or cantidad <= 0:
            raise ValidationError({"cantidad_requerida": "La cantidad requerida debe ser mayor que cero."})
        normalizadas.append((insumo, cantidad))
    if not normalizadas:
        raise ValidationError({"receta": "Agrega al menos un insumo a la receta."})
    try:
        with transaction.atomic():
            ProductoInsumo.objects.filter(producto=producto).delete()
            guardadas = []
            for insumo, cantidad in normalizadas:
                linea = ProductoInsumo(producto=producto, insumo=insumo, cantidad_requerida=cantidad)
                linea.full_clean()
                linea.save()
                guardadas.append(linea)
    except ProtectedError as error:
        logger.exception("No se pudo reemplazar la receta del producto %s.", producto.pk)
        raise ValidationError({"receta": "No se pudo actualizar la receta."}) from error
    logger.info("Se guardó la receta del producto %s.", producto.id_producto)
    return guardadas


def insumos_en_stock_bajo():
    """Devuelve insumos en el mínimo o por debajo."""
    return Insumo.objects.filter(cantidad_disponible__lte=F("stock_minimo")).order_by("nombre")


def productos_en_stock_bajo():
    """Devuelve productos Disponibles activos en el mínimo o por debajo."""
    return Producto.objects.filter(
        activo=True, tipo=Producto.Tipo.DISPONIBLE, stock_producto__lte=F("stock_minimo")
    ).order_by("nombre")


def calcular_requerimiento(*, producto, cantidad):
    """Calcula la cantidad exacta de cada insumo para unidades solicitadas."""
    cantidad = _cantidad_decimal(cantidad, "cantidad")
    return {
        linea.insumo: linea.cantidad_requerida * cantidad
        for linea in ProductoInsumo.objects.filter(producto=producto).select_related("insumo")
    }


def validar_disponibilidad(*, producto, cantidad):
    """Compara la cantidad solicitada con stock o con insumos de la receta."""
    cantidad = _cantidad_decimal(cantidad, "cantidad")
    if producto.tipo == Producto.Tipo.DISPONIBLE:
        disponible = Decimal(producto.stock_producto)
        faltante = max(Decimal("0"), cantidad - disponible)
        return faltante == 0, ({producto: faltante} if faltante else {})
    requerimientos = calcular_requerimiento(producto=producto, cantidad=cantidad)
    faltantes = {
        insumo: requerido - insumo.cantidad_disponible
        for insumo, requerido in requerimientos.items()
        if requerido > insumo.cantidad_disponible
    }
    return bool(requerimientos) and not faltantes, faltantes


def unidades_fabricables(*, producto):
    """Calcula el máximo de unidades completas que permite la receta actual."""
    lineas = ProductoInsumo.objects.filter(producto=producto).select_related("insumo")
    if not lineas.exists():
        return 0
    return min(int(linea.insumo.cantidad_disponible // linea.cantidad_requerida) for linea in lineas)
