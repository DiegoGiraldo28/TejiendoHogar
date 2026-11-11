"""Vistas de la Emprendedora: gestión de pedidos (maestro-detalle), avance de estado y cancelación."""
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.common.constants import TAMANO_PAGINA
from .models import Pedido
from .services import (
    ESTADOS_CANCELABLES_EMPRENDEDORA, ESTADOS_FILTRO, cambiar_estado, cancelar_pedido, conteos_por_estado,
    desglose_fecha_entrega, linea_de_estados, obtener_pedido_para_gestion, pedidos_para_gestion,
    siguiente_estado,
)

EMPRENDEDORA = Usuario.Rol.EMPRENDEDORA
# Una fecha estimada se resalta si vence en este número de días o menos.
DIAS_ALERTA_ENTREGA = 2
ESTADOS_ACTIVOS = [Pedido.Estado.CONFIRMADO, Pedido.Estado.EN_PREPARACION, Pedido.Estado.LISTO]
PARAMETROS_LISTA = ("estado", "q", "page")
# La pastilla de En_preparacion agrupa los pedidos «En preparación» y «En confección».
NOMBRES_FILTRO = {Pedido.Estado.EN_PREPARACION: "En preparación / confección"}


def _parametros_lista(datos) -> str:
    """Querystring de la lista (estado, búsqueda y página) para volver a la misma vista."""
    parametros = {clave: datos.get(clave) for clave in PARAMETROS_LISTA if datos.get(clave)}
    return urlencode(parametros)


def _con_parametros(url: str, parametros: str) -> str:
    return f"{url}?{parametros}" if parametros else url


def _pedido_o_404(pedido_id: int) -> Pedido:
    pedido = obtener_pedido_para_gestion(pedido_id=pedido_id)
    if pedido is None:
        raise Http404("Pedido no encontrado")
    return pedido


def _panel(pedido: Pedido) -> dict:
    siguiente = siguiente_estado(pedido=pedido)
    return {
        "pedido": pedido,
        "etapas": linea_de_estados(pedido=pedido, para_cliente=False),
        "siguiente": siguiente,
        "siguiente_nombre": pedido.nombre_de_estado(siguiente, para_cliente=False) if siguiente else "",
        "puede_cancelar": pedido.estado in ESTADOS_CANCELABLES_EMPRENDEDORA,
        "desglose": desglose_fecha_entrega(pedido=pedido),
        "detalles": pedido.detalles.all(),
        "movimientos": pedido.movimientos_insumo.all(),
    }


def _gestion(request, pedido_id: int | None = None):
    estado = request.GET.get("estado", "")
    if estado not in ESTADOS_FILTRO:
        estado = ""
    busqueda = request.GET.get("q", "").strip()
    pagina = Paginator(
        pedidos_para_gestion(estado=estado, busqueda=busqueda), TAMANO_PAGINA,
    ).get_page(request.GET.get("page"))
    conteos = conteos_por_estado(busqueda=busqueda)
    filtros = [{"valor": "", "nombre": "Todos", "conteo": conteos["todos"]}] + [
        {"valor": valor, "nombre": NOMBRES_FILTRO.get(valor, Pedido.Estado(valor).label), "conteo": conteos[valor]}
        for valor in ESTADOS_FILTRO
    ]
    contexto = {
        "pagina": pagina,
        "filtros": filtros,
        "estado": estado,
        "busqueda": busqueda,
        "parametros": _parametros_lista(request.GET),
        "campos_lista": [(clave, request.GET[clave]) for clave in PARAMETROS_LISTA if request.GET.get(clave)],
        "limite_alerta": timezone.localdate() + timedelta(days=DIAS_ALERTA_ENTREGA),
        "estados_activos": ESTADOS_ACTIVOS,
        "seleccionado": None,
    }
    if pedido_id is not None:
        seleccionado = _pedido_o_404(pedido_id)
        contexto.update(_panel(seleccionado), seleccionado=seleccionado)
    return render(request, "orders/gestion.html", contexto)


@rol_requerido(EMPRENDEDORA)
def gestion_pedidos(request):
    """Lista de pedidos con filtros por estado, búsqueda y paginación."""
    return _gestion(request)


@rol_requerido(EMPRENDEDORA)
def gestion_pedido(request, pedido_id):
    """La misma lista con el pedido seleccionado y su panel de detalle."""
    return _gestion(request, pedido_id)


@rol_requerido(EMPRENDEDORA)
@require_POST
def avanzar_pedido(request, pedido_id):
    """Avanza el pedido al estado enviado si es el siguiente; un segundo envío igual no avanza dos veces."""
    pedido = _pedido_o_404(pedido_id)
    try:
        actualizado = cambiar_estado(pedido=pedido, nuevo_estado=request.POST.get("nuevo_estado", ""),
                                     usuario=request.user)
    except ValidationError as error:
        for mensaje in error.messages:
            messages.error(request, mensaje)
    else:
        messages.success(
            request, f"El pedido {actualizado.numero_visible} pasó a «{actualizado.estado_emprendedora}».",
        )
    destino = reverse("orders:gestion_pedido", args=[pedido.pk])
    return redirect(_con_parametros(destino, _parametros_lista(request.POST)))


@rol_requerido(EMPRENDEDORA)
@require_http_methods(["GET", "POST"])
def cancelar_pedido_gestion(request, pedido_id):
    """Cancela un pedido Pendiente o Confirmado; con GET muestra la confirmación sin JavaScript."""
    pedido = _pedido_o_404(pedido_id)
    destino = _con_parametros(
        reverse("orders:gestion_pedido", args=[pedido.pk]),
        _parametros_lista(request.POST if request.method == "POST" else request.GET),
    )
    if request.method == "POST":
        try:
            cancelar_pedido(pedido=pedido, usuario=request.user)
        except ValidationError as error:
            for mensaje in error.messages:
                messages.error(request, mensaje)
        else:
            messages.success(request, f"Cancelaste el pedido {pedido.numero_visible}.")
        return redirect(destino)
    if pedido.estado not in ESTADOS_CANCELABLES_EMPRENDEDORA:
        messages.error(request, "Solo se pueden cancelar pedidos Pendientes o Confirmados.")
        return redirect(destino)
    return render(request, "orders/gestion_confirmar_cancelar.html", {
        "pedido": pedido, "volver": destino,
        "campos_lista": [(clave, request.GET[clave]) for clave in PARAMETROS_LISTA if request.GET.get(clave)],
    })
