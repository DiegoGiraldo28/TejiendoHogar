"""Vista del pedido provisional que no crea registros."""
from decimal import Decimal

from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.catalog.models import Producto
from apps.inventory.services import validar_disponibilidad
from .forms import PedidoEnProcesoForm


@rol_requerido(Usuario.Rol.CLIENTE)
@require_POST
def en_proceso(request):
    """Valida producto y cantidad; muestra el subtotal sin persistir el pedido."""
    formulario = PedidoEnProcesoForm(request.POST)
    if not formulario.is_valid():
        return render(request, "orders/en_proceso.html", {"form": formulario}, status=400)

    producto = formulario.cleaned_data["producto_id"]
    cantidad = formulario.cleaned_data["cantidad"]
    if producto.tipo == Producto.Tipo.DISPONIBLE:
        if cantidad > producto.stock_producto:
            formulario.add_error("cantidad", "La cantidad supera las unidades disponibles.")
            return render(request, "orders/en_proceso.html", {"form": formulario}, status=400)
    else:
        disponible, _ = validar_disponibilidad(producto=producto, cantidad=cantidad)
        if not disponible:
            formulario.add_error("cantidad", "No hay insumos suficientes para fabricar esta cantidad.")
            return render(request, "orders/en_proceso.html", {"form": formulario}, status=400)

    subtotal = producto.precio * Decimal(cantidad)
    return render(request, "orders/en_proceso.html", {
        "producto": producto,
        "cantidad": cantidad,
        "subtotal": subtotal,
        "confirmado": True,
    })
