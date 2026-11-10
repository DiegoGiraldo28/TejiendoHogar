"""Validadores compartidos por formularios y modelos."""
import re

from django.core.exceptions import ValidationError

PATRON_TELEFONO = r"[0-9+ ()-]{7,20}"
AYUDA_TELEFONO = "Entre 7 y 20 caracteres: números, espacios, +, - o paréntesis"


def validar_telefono(telefono: str) -> None:
    """Valida teléfonos de 7 a 20 caracteres permitidos."""
    if telefono and not re.fullmatch(PATRON_TELEFONO, telefono):
        raise ValidationError("Ingresa un teléfono válido (7 a 20 caracteres).")
