"""Pruebas de los ayudantes compartidos entre las aplicaciones."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from apps.common.formato import formatear_precio
from apps.common.forms import agregar_errores


class FormularioComun(forms.Form):
    nombre = forms.CharField()


def test_agregar_errores_mapea_campos_y_errores_generales():
    formulario = FormularioComun(data={"nombre": "válido"})
    assert formulario.is_valid()
    agregar_errores(formulario, ValidationError({"nombre": "Revisa el nombre.", "desconocido": "Dato inválido."}))
    assert "Revisa el nombre." in formulario.errors["nombre"]
    assert "Dato inválido." in formulario.non_field_errors()

    agregar_errores(formulario, ValidationError("Error general."))
    assert "Error general." in formulario.non_field_errors()


def test_formatear_precio_usa_punto_de_miles_y_cop_sin_espacios():
    assert formatear_precio(Decimal("89000.00")) == "$89.000 COP"
    assert formatear_precio(Decimal("1289000.50")) == "$1.289.001 COP"
    assert formatear_precio(0) == "$0 COP"
    assert formatear_precio(950) == "$950 COP"
    assert formatear_precio("no es número") == ""
