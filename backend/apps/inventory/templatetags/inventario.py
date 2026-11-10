"""Etiquetas disponibles para las plantillas del catálogo y del inventario."""
from django import template

from apps.common.constants import MAX_UNIDADES_SOBRE_PEDIDO
from apps.inventory.services import unidades_fabricables as calcular_unidades_fabricables

register = template.Library()


@register.simple_tag
def unidades_fabricables(producto):
    """Devuelve las unidades fabricables con los insumos registrados."""
    return calcular_unidades_fabricables(producto=producto)


@register.simple_tag
def max_unidades_sobre_pedido():
    """Expone el límite de unidades del formulario de pedido."""
    return MAX_UNIDADES_SOBRE_PEDIDO
