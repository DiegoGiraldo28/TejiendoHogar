"""Formatos de presentación compartidos."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any


def formatear_precio(valor: Any) -> str:
    """Devuelve el precio como «$89.000 COP»: pesos enteros y punto como separador de miles."""
    try:
        pesos = Decimal(str(valor)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    signo = "-" if pesos < 0 else ""
    return f"{signo}${abs(int(pesos)):,} COP".replace(",", ".")
