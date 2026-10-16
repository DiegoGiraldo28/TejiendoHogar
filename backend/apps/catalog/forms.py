"""Formularios para los productos del taller."""
from django import forms

from .models import Producto


class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = [
            "nombre", "precio", "tipo", "descripcion", "imagen",
            "tiempo_produccion_dias", "stock_producto", "stock_minimo",
        ]
        labels = {
            "nombre": "Nombre del producto", "precio": "Precio (COP)",
            "tipo": "Tipo de disponibilidad", "descripcion": "Descripción",
            "imagen": "Imagen del producto", "tiempo_produccion_dias": "Días de confección",
            "stock_producto": "Unidades en stock", "stock_minimo": "Stock mínimo",
        }
        help_texts = {
            "nombre": "Usa un nombre claro y fácil de encontrar.",
            "descripcion": "Describe la prenda, el material y sus detalles.",
            "imagen": "Formatos JPG, PNG o WEBP; máximo 2 MB.",
            "tiempo_produccion_dias": "Tiempo estimado de confección por unidad.",
        }
        widgets = {
            "precio": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "tipo": forms.Select(),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "imagen": forms.FileInput(),
            "tiempo_produccion_dias": forms.NumberInput(attrs={"min": "1", "step": "1"}),
            "stock_producto": forms.NumberInput(attrs={"min": "0", "step": "1"}),
            "stock_minimo": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["imagen"].required = False
        for nombre, field in self.fields.items():
            auto_id = self[nombre].auto_id
            ids = [f"{auto_id}_help", f"{auto_id}_errors"]
            field.widget.attrs["aria-describedby"] = " ".join(ids)


class ConfirmarProductoForm(forms.Form):
    """Form vacío para que las eliminaciones solo sucedan con POST."""
