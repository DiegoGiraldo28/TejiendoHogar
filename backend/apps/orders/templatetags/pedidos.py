"""Etiquetas de pedidos para plantillas de otras apps (por ejemplo, el perfil de la Emprendedora).

`accounts` no importa `orders` en Python; sus plantillas pueden usar `{% load pedidos %}`, igual que
`catalog` usa `{% load inventario %}`.
"""
from django import template

from apps.orders.services import piezas_entregadas as calcular_piezas_entregadas

register = template.Library()


@register.simple_tag
def piezas_entregadas():
    """Piezas entregadas por el taller (suma de cantidades de pedidos Entregados)."""
    return calcular_piezas_entregadas()
