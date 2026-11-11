"""Ayudantes propios de las pruebas de pedidos; reutilizan los de backend/conftest.py."""
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.catalog.models import Producto
from apps.inventory.models import Insumo
from apps.inventory.services import crear_insumo, guardar_receta
from conftest import crear_producto_prueba

DIRECCION = "Calle 127 # 15-40, Bogotá"
TELEFONO = "310 456 7890"


class SesionPrueba(dict):
    """Sesión mínima en memoria para probar la bolsa sin peticiones HTTP."""
    modified = False


def disponible(*, nombre="Blusa de lino", precio="45000", stock=5, dias=3):
    return crear_producto_prueba(
        nombre=nombre, precio=precio, tipo=Producto.Tipo.DISPONIBLE,
        tiempo_produccion_dias=dias, stock_producto=stock,
    )


def sobre_pedido(*, nombre="Vestido midi", precio="150000", dias=4, insumo=None, requerido="2",
                 cantidad_insumo="10"):
    """Crea un Sobre pedido activo con receta de un insumo (nuevo o existente)."""
    producto = crear_producto_prueba(
        nombre=nombre, precio=precio, tipo=Producto.Tipo.SOBRE_PEDIDO,
        tiempo_produccion_dias=dias, stock_producto=0,
    )
    if insumo is None:
        insumo = crear_insumo(
            nombre=f"Tela para {nombre}", unidad_medida=Insumo.Unidad.METROS,
            cantidad_disponible=cantidad_insumo,
        )
    guardar_receta(producto=producto, lineas=[{"insumo": insumo, "cantidad_requerida": Decimal(requerido)}])
    producto.activo = True
    producto.save(update_fields=["activo"])
    return producto


def otra_cliente(correo="otra@example.com"):
    return get_user_model().objects.create_user(correo, "ClaveFuerte-2026", nombre="Otra Cliente")
