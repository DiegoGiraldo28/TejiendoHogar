"""Formularios de inventario y recetas."""
from django import forms
from django.forms import inlineformset_factory

from apps.catalog.models import Producto
from .models import Insumo, MovimientoInsumo, ProductoInsumo


def _conectar_ayudas(formulario):
    for nombre, campo in formulario.fields.items():
        auto_id = formulario[nombre].auto_id
        campo.widget.attrs["aria-describedby"] = f"{auto_id}_help {auto_id}_errors"


class InsumoForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ["nombre", "unidad_medida", "cantidad_disponible", "stock_minimo"]
        labels = {"nombre": "Nombre de la materia prima", "unidad_medida": "Unidad de medida", "cantidad_disponible": "Cantidad", "stock_minimo": "Stock mínimo"}
        help_texts = {"cantidad_disponible": "Si ingresas una cantidad inicial, se registrará como una entrada."}
        widgets = {
            "cantidad_disponible": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "stock_minimo": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _conectar_ayudas(self)


class InsumoEdicionForm(forms.ModelForm):
    class Meta:
        model = Insumo
        fields = ["nombre", "unidad_medida", "stock_minimo"]
        labels = {"nombre": "Nombre de la materia prima", "unidad_medida": "Unidad de medida", "stock_minimo": "Stock mínimo"}
        widgets = {"stock_minimo": forms.NumberInput(attrs={"min": "0", "step": "0.01"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _conectar_ayudas(self)


class EntradaForm(forms.Form):
    cantidad = forms.DecimalField(min_value=0.01, max_digits=10, decimal_places=2, label="Cantidad que ingresa", widget=forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _conectar_ayudas(self)


class ProductoInsumoForm(forms.ModelForm):
    class Meta:
        model = ProductoInsumo
        fields = ["insumo", "cantidad_requerida"]
        labels = {"insumo": "Insumo", "cantidad_requerida": "Cantidad por unidad"}
        widgets = {"cantidad_requerida": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["insumo"].queryset = Insumo.objects.order_by("nombre")
        _conectar_ayudas(self)


RecetaFormSet = inlineformset_factory(
    Producto, ProductoInsumo, form=ProductoInsumoForm,
    fk_name="producto", extra=1, can_delete=True,
)


class MovimientoFiltroForm(forms.Form):
    tipo_movimiento = forms.ChoiceField(required=False, choices=[("", "Todos los movimientos"), *MovimientoInsumo.Tipo.choices], label="Tipo de movimiento")
