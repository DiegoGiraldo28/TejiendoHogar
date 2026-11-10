"""Formulario de datos de entrega del paso 1 (Bolsa y envío)."""
from django import forms

from apps.common.validators import AYUDA_TELEFONO, PATRON_TELEFONO, validar_telefono

AYUDA_DIRECCION = "Calle o carrera, número, barrio y ciudad"


class EntregaForm(forms.Form):
    telefono = forms.CharField(
        label="Teléfono de contacto", min_length=7, max_length=20, help_text=AYUDA_TELEFONO,
        error_messages={"required": "Ingresa un teléfono de contacto."},
        widget=forms.TextInput(attrs={
            "inputmode": "tel", "autocomplete": "tel", "pattern": PATRON_TELEFONO,
            "minlength": "7", "maxlength": "20",
        }),
    )
    direccion = forms.CharField(
        label="Dirección completa", max_length=255, help_text=AYUDA_DIRECCION,
        error_messages={"required": "Ingresa la dirección de entrega."},
        widget=forms.TextInput(attrs={"autocomplete": "street-address", "maxlength": "255"}),
    )

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        validar_telefono(telefono)
        return telefono
