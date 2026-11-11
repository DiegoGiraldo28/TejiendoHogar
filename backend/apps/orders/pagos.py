"""Pasarela de pago intercambiable. El pago actual es simulado: no se procesa dinero real."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


@dataclass(frozen=True)
class ResultadoPago:
    """Resultado de un cobro: exitoso o fallido, con un mensaje para la Cliente."""
    exitoso: bool
    mensaje: str


class PasarelaPago(ABC):
    """Interfaz de cobro usada por los servicios de pedidos.

    Para integrar una pasarela real (por ejemplo, Mercado Pago), crear otro adaptador que implemente
    esta interfaz.
    """

    @abstractmethod
    def cobrar(self, *, pedido: Any, datos: dict[str, Any]) -> ResultadoPago:
        """Cobra el total del pedido con los datos que necesite la pasarela."""


class PasarelaSimulada(PasarelaPago):
    """Simula el cobro según datos["simular_exito"]; no guarda ni pide datos de pago."""

    def cobrar(self, *, pedido: Any, datos: dict[str, Any]) -> ResultadoPago:
        if datos.get("simular_exito"):
            return ResultadoPago(exitoso=True, mensaje="Pago aprobado (simulado).")
        return ResultadoPago(exitoso=False, mensaje="Fondos insuficientes (simulado).")


PASARELAS = {"simulada": PasarelaSimulada}


def obtener_pasarela() -> PasarelaPago:
    """Devuelve la pasarela configurada en el ajuste PASARELA_PAGO."""
    nombre = getattr(settings, "PASARELA_PAGO", "simulada")
    try:
        return PASARELAS[nombre]()
    except KeyError as error:
        raise ImproperlyConfigured(f"Pasarela de pago desconocida: {nombre}.") from error
