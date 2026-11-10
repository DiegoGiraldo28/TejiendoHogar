"""Vistas de la Cliente: bolsa, pago simulado, Mis pedidos y seguimiento."""
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.catalog.models import Producto
from apps.common.constants import TAMANO_PAGINA
from apps.common.forms import agregar_errores
from .carrito import Bolsa, tope_producto
from .forms import EntregaForm
from .models import Pedido
from .services import (
    PedidoYaConfirmado, cancelar_pedido, estimar_fecha_entrega, linea_de_estados, obtener_pedido_de_cliente,
    pagar_y_confirmar, pedidos_de_cliente, preparar_pedido_desde_bolsa,
)

CLIENTE = Usuario.Rol.CLIENTE


def _mensajes_error(request, error: ValidationError) -> None:
    for mensaje in error.messages:
        messages.error(request, mensaje)


def _pedido_o_404(request, pedido_id: int) -> Pedido:
    pedido = obtener_pedido_de_cliente(cliente=request.user, pedido_id=pedido_id)
    if pedido is None:
        raise Http404("Pedido no encontrado")
    return pedido


@require_POST
def bolsa_agregar(request, producto_id):
    """Agrega un producto a la bolsa («Comprar ahora» o «Agregar a la bolsa») o ajusta la cantidad elegida."""
    detalle = reverse("catalog:detalle", args=[producto_id])
    if not request.user.is_authenticated:
        return redirect_to_login(detalle)
    if request.user.rol != CLIENTE:
        raise PermissionDenied
    producto = Producto.objects.filter(pk=producto_id, activo=True).first()
    if producto is None:
        messages.error(request, "El producto ya no está disponible.")
        return redirect("catalog:lista")
    accion = request.POST.get("accion", "agregar")
    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        cantidad = 1
    if accion in ("menos", "mas"):
        cantidad += 1 if accion == "mas" else -1
        cantidad = max(1, min(cantidad, max(tope_producto(producto), 1)))
        return redirect(f"{detalle}?{urlencode({'cantidad': cantidad})}#comprar")
    try:
        Bolsa(request.session).agregar(producto=producto, cantidad=cantidad)
    except ValidationError as error:
        _mensajes_error(request, error)
        return redirect(detalle)
    if accion == "comprar":
        return redirect("orders:bolsa")
    messages.success(request, f"Agregaste {producto.nombre} a tu bolsa.")
    return redirect(detalle)


@rol_requerido(CLIENTE)
@require_http_methods(["GET", "POST"])
def bolsa(request):
    """Paso 1: productos, cantidades y datos de entrega en un solo formulario."""
    carrito = Bolsa(request.session)
    if request.method == "POST":
        carrito.guardar_borrador(
            direccion=request.POST.get("direccion", ""), telefono=request.POST.get("telefono", ""),
        )
        accion, _, producto_id = request.POST.get("accion", "").partition(":")
        if accion in ("mas", "menos", "quitar"):
            producto = Producto.objects.filter(pk=producto_id).first() if producto_id.isdigit() else None
            if producto is not None:
                try:
                    if accion == "quitar":
                        carrito.quitar(producto_id=producto.pk)
                    else:
                        actual = carrito.cantidad_de(producto.pk)
                        carrito.actualizar(producto=producto, cantidad=actual + (1 if accion == "mas" else -1))
                except ValidationError as error:
                    _mensajes_error(request, error)
            return redirect("orders:bolsa")
        formulario = EntregaForm(request.POST)
        lineas = carrito.lineas()
        if not lineas:
            messages.error(request, "Tu bolsa está vacía.")
            return redirect("orders:bolsa")
        if formulario.is_valid():
            try:
                pedido = preparar_pedido_desde_bolsa(
                    cliente=request.user, bolsa=carrito,
                    direccion=formulario.cleaned_data["direccion"], telefono=formulario.cleaned_data["telefono"],
                )
            except ValidationError as error:
                agregar_errores(formulario, error)
            else:
                return redirect("orders:pago", pedido_id=pedido.pk)
    else:
        borrador = carrito.borrador()
        formulario = EntregaForm(initial={
            "direccion": borrador.get("direccion", request.user.direccion or ""),
            "telefono": borrador.get("telefono", request.user.telefono or ""),
        })
        lineas = carrito.lineas()
    total = sum((linea.subtotal for linea in lineas), 0)
    return render(request, "orders/bolsa.html", {
        "form": formulario,
        "lineas": lineas,
        "unidades": sum(linea.cantidad for linea in lineas),
        "total": total,
        "fecha_estimada": estimar_fecha_entrega(lineas=lineas) if lineas else None,
        "paso": 1,
    })


@rol_requerido(CLIENTE)
@require_http_methods(["GET", "POST"])
def pago(request, pedido_id):
    """Paso 2: pago simulado de un pedido Pendiente de la Cliente."""
    pedido = _pedido_o_404(request, pedido_id)
    if pedido.estado != Pedido.Estado.PENDIENTE:
        if pedido.estado == Pedido.Estado.CANCELADO:
            messages.info(request, "Este pedido fue cancelado.")
        else:
            messages.info(request, "Tu pedido ya fue confirmado.")
        return redirect("orders:seguimiento", pedido_id=pedido.pk)
    if request.method == "POST":
        try:
            resultado = pagar_y_confirmar(
                pedido=pedido, simular_exito=request.POST.get("resultado") == "exitoso", usuario=request.user,
            )
        except PedidoYaConfirmado:
            messages.info(request, "Tu pedido ya fue confirmado.")
            return redirect("orders:seguimiento", pedido_id=pedido.pk)
        except ValidationError as error:
            _mensajes_error(request, error)
            return redirect("orders:pago", pedido_id=pedido.pk)
        if resultado.estado == Pedido.Estado.CONFIRMADO:
            carrito = Bolsa(request.session)
            if carrito.pedido_pendiente_id == pedido.pk:
                carrito.vaciar()
            messages.success(request, "¡Pago simulado exitoso! Tu pedido quedó confirmado.")
            return redirect("orders:seguimiento", pedido_id=pedido.pk)
        messages.error(request, f"{resultado.resultado_pago.mensaje} Puedes reintentar el pago o cancelar el pedido.")
        return redirect("orders:pago", pedido_id=pedido.pk)
    return render(request, "orders/pago.html", {
        "pedido": pedido,
        "detalles": pedido.detalles.all(),
        "unidades": sum(detalle.cantidad for detalle in pedido.detalles.all()),
        "fecha_estimada": estimar_fecha_entrega(lineas=pedido.detalles.all()),
        "paso": 2,
    })


@rol_requerido(CLIENTE)
def mis_pedidos(request):
    """Lista paginada de los pedidos de la Cliente."""
    pagina = Paginator(pedidos_de_cliente(cliente=request.user), TAMANO_PAGINA).get_page(request.GET.get("page"))
    return render(request, "orders/mis_pedidos.html", {"pagina": pagina})


@rol_requerido(CLIENTE)
def seguimiento(request, pedido_id):
    """Paso 3: seguimiento del pedido con su fecha estimada y su línea de estados."""
    pedido = _pedido_o_404(request, pedido_id)
    detalles = pedido.detalles.all()
    return render(request, "orders/seguimiento.html", {
        "pedido": pedido,
        "detalles": detalles,
        "unidades": sum(detalle.cantidad for detalle in detalles),
        "etapas": linea_de_estados(pedido=pedido),
        "ultimo_cambio": list(pedido.historial.all())[-1].fecha_cambio if pedido.historial.all() else None,
        "fecha_estimada": (
            estimar_fecha_entrega(lineas=detalles) if pedido.estado == Pedido.Estado.PENDIENTE else None
        ),
        "paso": 3,
    })


@rol_requerido(CLIENTE)
@require_http_methods(["GET", "POST"])
def cancelar(request, pedido_id):
    """Cancela un pedido Pendiente de la Cliente; con GET muestra la confirmación sin JavaScript."""
    pedido = _pedido_o_404(request, pedido_id)
    if request.method == "POST":
        try:
            cancelar_pedido(pedido=pedido, usuario=request.user)
        except ValidationError as error:
            _mensajes_error(request, error)
        else:
            carrito = Bolsa(request.session)
            if carrito.pedido_pendiente_id == pedido.pk:
                carrito.pedido_pendiente_id = None
            messages.success(request, f"Cancelaste el pedido {pedido.numero_visible}.")
        return redirect("orders:seguimiento", pedido_id=pedido.pk)
    if pedido.estado != Pedido.Estado.PENDIENTE:
        messages.error(request, "Solo puedes cancelar pedidos que están en espera de pago.")
        return redirect("orders:seguimiento", pedido_id=pedido.pk)
    return render(request, "orders/confirmar_cancelar.html", {"pedido": pedido})
