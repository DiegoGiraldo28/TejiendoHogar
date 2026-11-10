"""Formulario para validar el pedido provisional sin guardar datos."""
from django import forms

from apps.common.constants import MAX_UNIDADES_SOBRE_PEDIDO
from apps.catalog.models import Producto


class PedidoEnProcesoForm(forms.Form):
    producto_id = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.HiddenInput(),
        error_messages={"invalid_choice": "El producto ya no está disponible."},
    )
    cantidad = forms.IntegerField(
        min_value=1, max_value=MAX_UNIDADES_SOBRE_PEDIDO, label="Cantidad",
        error_messages={
            "max_value": f"Puedes solicitar máximo {MAX_UNIDADES_SOBRE_PEDIDO} unidades por pedido."
        },
    )
