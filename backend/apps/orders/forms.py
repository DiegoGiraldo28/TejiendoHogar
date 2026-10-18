"""Formulario para validar el pedido provisional sin guardar datos."""
from django import forms

from apps.catalog.models import Producto


class PedidoEnProcesoForm(forms.Form):
    producto_id = forms.ModelChoiceField(
        queryset=Producto.objects.filter(activo=True),
        widget=forms.HiddenInput(),
        error_messages={"invalid_choice": "El producto ya no está disponible."},
    )
    cantidad = forms.IntegerField(min_value=1, label="Cantidad")
