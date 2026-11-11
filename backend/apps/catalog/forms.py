"""Formularios para los productos del taller."""
from django import forms

from .models import DIAS_PRODUCCION_DISPONIBLE, LIMITE_IMAGEN_BYTES, MINIMO_IMAGEN_PIXELES, PRECIO_MINIMO, Producto


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
            "precio": f"Precio igual o mayor que {PRECIO_MINIMO} COP.",
            "imagen": (
                f"Formatos JPG, PNG o WEBP; máximo {LIMITE_IMAGEN_BYTES // (1024 * 1024)} MB "
                f"y mínimo {MINIMO_IMAGEN_PIXELES} × {MINIMO_IMAGEN_PIXELES} px."
            ),
            "tiempo_produccion_dias": "Solo para Sobre pedido: días de confección por unidad, mínimo 1.",
            "stock_producto": "Stock disponible: mínimo 0 unidades.",
            "stock_minimo": "Stock mínimo: mínimo 0 unidades.",
        }
        widgets = {
            "precio": forms.NumberInput(attrs={"min": str(PRECIO_MINIMO), "step": "0.01"}),
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
        self.fields["stock_producto"].required = False
        self.fields["stock_minimo"].required = False
        self.fields["tiempo_produccion_dias"].required = False
        self.fields["imagen"].widget.attrs["accept"] = ".jpg,.jpeg,.png,.webp"
        for nombre, field in self.fields.items():
            auto_id = self[nombre].auto_id
            ids = [f"{auto_id}_help", f"{auto_id}_errors"]
            field.widget.attrs["aria-describedby"] = " ".join(ids)
        self.fields["tipo"].widget.attrs.update({
            "data-tipo-disponible": Producto.Tipo.DISPONIBLE,
            "data-tipo-sobre-pedido": Producto.Tipo.SOBRE_PEDIDO,
        })

    def clean(self):
        datos = super().clean()
        if datos.get("tipo") == Producto.Tipo.SOBRE_PEDIDO:
            datos["stock_producto"] = 0
            datos["stock_minimo"] = 0
            if datos.get("tiempo_produccion_dias") is None and "tiempo_produccion_dias" not in self.errors:
                self.add_error("tiempo_produccion_dias", "Este campo es obligatorio para un producto Sobre pedido.")
        elif datos.get("tipo") == Producto.Tipo.DISPONIBLE:
            datos["tiempo_produccion_dias"] = DIAS_PRODUCCION_DISPONIBLE
            self.errors.pop("tiempo_produccion_dias", None)
            for nombre in ("stock_producto", "stock_minimo"):
                if datos.get(nombre) is None:
                    self.add_error(nombre, "Este campo es obligatorio para un producto Disponible.")
        return datos
