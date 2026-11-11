"""Crea 4 pedidos de ejemplo en estados distintos para la primera Cliente que exista.

Usa los servicios del proceso (crear, pagar, avanzar), así que descuenta stock e insumos como un pedido
real. No crea usuarios ni contraseñas. Lo llama `cargar_datos_demo` después de crear productos e insumos.
"""
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand

from apps.accounts.models import Usuario
from apps.catalog.models import Producto
from apps.common.validators import validar_telefono
from apps.orders.models import Pedido
from apps.orders.services import cambiar_estado, crear_pedido, pagar_y_confirmar

DIRECCION_DEMO = "Calle 10 # 5-20, Tunja"
TELEFONO_DEMO = "3001234567"

# (producto, cantidad, estados a los que avanza tras confirmar; None = queda Pendiente)
PEDIDOS_DEMO = [
    ("Blusa lino natural", 1, None),
    ("Pantalón lino recto", 1, []),
    ("Chaqueta tejida a mano", 1, [Pedido.Estado.EN_PREPARACION]),
    ("Camisa artesanal a rayas", 2, [Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO, Pedido.Estado.ENTREGADO]),
]


def _telefono(cliente: Usuario) -> str:
    """Teléfono del perfil si es válido; si falta o no es válido, uno de demostración."""
    if not (cliente.telefono or "").strip():
        return TELEFONO_DEMO
    try:
        validar_telefono(cliente.telefono)
    except ValidationError:
        return TELEFONO_DEMO
    return cliente.telefono


class Command(BaseCommand):
    help = "Crea pedidos de ejemplo para la primera Cliente; no crea usuarios y puede ejecutarse varias veces."

    def handle(self, *args, **options):
        cliente = Usuario.objects.filter(rol=Usuario.Rol.CLIENTE).order_by("pk").first()
        if cliente is None:
            self.stdout.write(self.style.WARNING(
                "No hay ninguna cuenta Cliente: se omiten los pedidos de ejemplo. Registra una Cliente y "
                "vuelve a ejecutar el comando."
            ))
            return
        if Pedido.objects.filter(cliente=cliente).exists():
            self.stdout.write(f"La Cliente {cliente.correo} ya tiene pedidos: no se crean pedidos de ejemplo.")
            return
        emprendedora = Usuario.objects.filter(rol=Usuario.Rol.EMPRENDEDORA).order_by("pk").first()
        creados = 0
        for nombre, cantidad, avances in PEDIDOS_DEMO:
            producto = Producto.objects.filter(nombre=nombre, activo=True).first()
            if producto is None:
                self.stdout.write(self.style.WARNING(f"Se omite el pedido de «{nombre}»: el producto no está activo."))
                continue
            try:
                pedido = crear_pedido(
                    cliente=cliente, lineas=[{"producto": producto, "cantidad": cantidad}],
                    direccion=(cliente.direccion or "").strip() or DIRECCION_DEMO, telefono=_telefono(cliente),
                )
                if avances is not None:
                    pedido = pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
                    if avances and emprendedora is None:
                        self.stdout.write(self.style.WARNING(
                            f"No hay Emprendedora: el pedido {pedido.numero_visible} queda Confirmado."
                        ))
                        avances = []
                    for estado in avances:
                        pedido = cambiar_estado(pedido=pedido, nuevo_estado=estado, usuario=emprendedora)
            except ValidationError as error:
                self.stdout.write(self.style.WARNING(f"Se omite el pedido de «{nombre}»: {' '.join(error.messages)}"))
                continue
            creados += 1
        self.stdout.write(self.style.SUCCESS(f"Pedidos de ejemplo creados para {cliente.correo}: {creados}."))
