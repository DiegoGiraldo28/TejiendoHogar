"""Filtro de precios para el catálogo y los pedidos: «$89.000 COP»."""
from django import template

from apps.common.formato import formatear_precio

register = template.Library()


@register.filter
def precio(valor):
    """Formatea un precio en pesos colombianos con el formato único de la aplicación."""
    return formatear_precio(valor)
