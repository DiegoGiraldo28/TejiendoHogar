"""Pruebas de los ayudantes compartidos entre las aplicaciones."""
from django import forms
from django.core.exceptions import ValidationError

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
