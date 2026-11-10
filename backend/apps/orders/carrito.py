"""Bolsa de compra guardada en la sesión del servidor (RNF-18).

La sesión usa la cookie persistente de Django: la bolsa se conserva al cerrar el navegador y se
vacía al cerrar sesión. Los precios nunca se guardan aquí: se recalculan en el servidor.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError

from apps.catalog.models import Producto
from apps.common.constants import MAX_UNIDADES_SOBRE_PEDIDO

CLAVE_BOLSA = "bolsa"
CLAVE_BORRADOR = "bolsa_entrega"
CLAVE_PEDIDO_PENDIENTE = "bolsa_pedido_pendiente"


@dataclass
class LineaBolsa:
    """Línea de la bolsa con el precio actual del producto."""
    producto: Producto
    cantidad: int

    @property
    def precio(self) -> Decimal:
        return self.producto.precio

    @property
    def subtotal(self) -> Decimal:
        return self.producto.precio * self.cantidad

    @property
    def tope(self) -> int:
        return tope_producto(self.producto)


def tope_producto(producto: Producto) -> int:
    """Máximo de unidades por producto: el stock (Disponible) o MAX_UNIDADES_SOBRE_PEDIDO."""
    if producto.tipo == Producto.Tipo.DISPONIBLE:
        return producto.stock_producto
    return MAX_UNIDADES_SOBRE_PEDIDO


def validar_cantidad(*, producto: Producto, cantidad: Any, validar_stock: bool = True) -> int:
    """Valida que el producto esté activo y que la cantidad respete su tope.

    Con validar_stock=False no compara con el stock de un Disponible: crear_pedido lo valida
    después para registrar el RechazoPedido correspondiente.
    """
    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError) as error:
        raise ValidationError({"cantidad": "Ingresa una cantidad válida."}) from error
    if not producto.activo:
        raise ValidationError({"producto": "El producto ya no está disponible."})
    if cantidad < 1:
        raise ValidationError({"cantidad": "La cantidad mínima es 1."})
    tope = tope_producto(producto)
    if producto.tipo == Producto.Tipo.DISPONIBLE and not validar_stock:
        return cantidad
    if producto.tipo == Producto.Tipo.DISPONIBLE and cantidad > tope:
        if tope == 0:
            raise ValidationError({"cantidad": f"{producto.nombre} está agotado por el momento."})
        raise ValidationError({"cantidad": f"Solo hay {tope} unidades disponibles de {producto.nombre}."})
    if cantidad > tope:
        raise ValidationError({"cantidad": f"Puedes solicitar máximo {tope} unidades de {producto.nombre}."})
    return cantidad


class Bolsa:
    """Operaciones sobre la bolsa de la Cliente guardada en request.session."""

    def __init__(self, session):
        self.session = session

    def _items(self) -> dict[str, int]:
        return dict(self.session.get(CLAVE_BOLSA, {}))

    def _guardar(self, items: dict[str, int]) -> None:
        self.session[CLAVE_BOLSA] = items
        self.session.modified = True

    def cantidad_de(self, producto_id: int) -> int:
        return self._items().get(str(producto_id), 0)

    def agregar(self, *, producto: Producto, cantidad: Any = 1) -> int:
        """Suma unidades a la línea del producto respetando el tope; devuelve la cantidad final."""
        items = self._items()
        nueva = self.cantidad_de(producto.pk) + int(cantidad)
        items[str(producto.pk)] = validar_cantidad(producto=producto, cantidad=nueva)
        self._guardar(items)
        return items[str(producto.pk)]

    def actualizar(self, *, producto: Producto, cantidad: Any) -> int:
        """Fija la cantidad de una línea; con 0 o menos la quita."""
        try:
            entero = int(cantidad)
        except (TypeError, ValueError) as error:
            raise ValidationError({"cantidad": "Ingresa una cantidad válida."}) from error
        if entero < 1:
            self.quitar(producto_id=producto.pk)
            return 0
        items = self._items()
        items[str(producto.pk)] = validar_cantidad(producto=producto, cantidad=entero)
        self._guardar(items)
        return entero

    def quitar(self, *, producto_id: int) -> None:
        items = self._items()
        items.pop(str(producto_id), None)
        self._guardar(items)

    def vaciar(self) -> None:
        """Vacía productos, borrador de entrega y pedido pendiente asociado."""
        for clave in (CLAVE_BOLSA, CLAVE_BORRADOR, CLAVE_PEDIDO_PENDIENTE):
            self.session.pop(clave, None)
        self.session.modified = True

    def lineas(self) -> list[LineaBolsa]:
        """Lista las líneas con precio actual en una sola consulta; descarta productos inactivos o borrados."""
        items = self._items()
        if not items:
            return []
        productos = Producto.objects.filter(pk__in=[int(pk) for pk in items], activo=True).in_bulk()
        lineas = []
        for pk, cantidad in items.items():
            producto = productos.get(int(pk))
            if producto is not None:
                lineas.append(LineaBolsa(producto=producto, cantidad=min(cantidad, max(tope_producto(producto), 1))))
        if len(lineas) != len(items) or any(items[str(linea.producto.pk)] != linea.cantidad for linea in lineas):
            self._guardar({str(linea.producto.pk): linea.cantidad for linea in lineas})
        return lineas

    @property
    def total_unidades(self) -> int:
        """Unidades en la bolsa, leídas de la sesión sin consultar la base de datos."""
        return sum(self._items().values())

    def borrador(self) -> dict[str, str]:
        return dict(self.session.get(CLAVE_BORRADOR, {}))

    def guardar_borrador(self, *, direccion: str, telefono: str) -> None:
        """Guarda lo que la Cliente escribió para no perderlo al cambiar cantidades."""
        self.session[CLAVE_BORRADOR] = {"direccion": direccion, "telefono": telefono}
        self.session.modified = True

    @property
    def pedido_pendiente_id(self) -> int | None:
        return self.session.get(CLAVE_PEDIDO_PENDIENTE)

    @pedido_pendiente_id.setter
    def pedido_pendiente_id(self, valor: int | None) -> None:
        if valor is None:
            self.session.pop(CLAVE_PEDIDO_PENDIENTE, None)
        else:
            self.session[CLAVE_PEDIDO_PENDIENTE] = valor
        self.session.modified = True
