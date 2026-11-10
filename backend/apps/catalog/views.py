"""Vistas de gestión y catálogo público de productos."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.accounts.views import destino_rol
from apps.common.constants import TAMANO_PAGINA
from apps.common.forms import agregar_errores
from .forms import ProductoForm
from .models import Producto
from .services import (
    actualizar_producto, cambiar_estado, crear_producto, eliminar_producto,
    listar_admin, listar_publicos, obtener_publico, productos_destacados,
)


def inicio(request):
    if request.user.is_authenticated:
        return redirect(destino_rol(request.user))
    return render(request, "inicio.html", {"destacados": productos_destacados()})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def lista_productos(request):
    productos = listar_admin(
        busqueda=request.GET.get("q", ""),
        estado=request.GET.get("estado", ""),
        tipo=request.GET.get("tipo", ""),
    )
    pagina = Paginator(productos, TAMANO_PAGINA).get_page(request.GET.get("page"))
    return render(request, "catalog/productos.html", {"pagina": pagina})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def producto_nuevo(request):
    formulario = ProductoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            producto = crear_producto(**formulario.cleaned_data)
        except ValidationError as error:
            agregar_errores(formulario, error)
        else:
            messages.success(
                request,
                "Producto creado. Paso 2: define su receta con los insumos que tienes registrados.",
            )
            if producto.tipo == Producto.Tipo.SOBRE_PEDIDO:
                return redirect("inventory:receta", producto_id=producto.pk)
            return redirect("catalog:productos")
    return render(request, "catalog/producto_form.html", {
        "form": formulario, "titulo": "Nuevo producto",
        "mostrar_aviso_imagen": request.method == "POST" and not formulario.is_valid(),
    })


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def producto_editar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    formulario = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if request.method == "POST" and formulario.is_valid():
        try:
            actualizar_producto(producto=producto, **formulario.cleaned_data)
        except ValidationError as error:
            agregar_errores(formulario, error)
        else:
            messages.success(request, "Producto actualizado correctamente.")
            return redirect("catalog:productos")
    return render(request, "catalog/producto_form.html", {
        "form": formulario, "producto": producto, "titulo": "Editar producto",
        "mostrar_aviso_imagen": request.method == "POST" and not formulario.is_valid()
        and bool(request.FILES.get("imagen")),
    })


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
@require_POST
def producto_estado(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    try:
        cambiar_estado(producto=producto)
    except ValidationError as error:
        for mensajes in error.message_dict.values():
            for mensaje in mensajes:
                messages.error(request, mensaje)
    else:
        estado = "activado" if producto.activo else "desactivado"
        messages.success(request, f"Producto {estado} correctamente.")
    return redirect("catalog:productos")


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def producto_eliminar(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    if request.method == "POST":
        try:
            eliminar_producto(producto=producto)
        except ValidationError as error:
            for mensajes in error.message_dict.values():
                for mensaje in mensajes:
                    messages.error(request, mensaje)
        else:
            messages.success(request, "Producto eliminado correctamente.")
        return redirect("catalog:productos")
    return render(request, "catalog/producto_confirmar_eliminar.html", {"producto": producto})


def lista(request):
    """Muestra productos activos con búsqueda, filtro y paginación."""
    busqueda = request.GET.get("q", "").strip()
    tipo = request.GET.get("tipo", "")
    pagina = Paginator(listar_publicos(busqueda=busqueda, tipo=tipo), TAMANO_PAGINA).get_page(
        request.GET.get("page"))
    return render(request, "catalog/lista.html", {
        "pagina": pagina,
        "busqueda": busqueda,
        "tipo_seleccionado": tipo if tipo in Producto.Tipo.values else "",
        "tipos": Producto.Tipo.choices,
    })


def detalle(request, producto_id):
    """Muestra un producto activo o responde 404 si está oculto."""
    producto = obtener_publico(id_producto=producto_id)
    if producto is None:
        raise Http404("Producto no encontrado")
    return render(request, "catalog/detalle.html", {"producto": producto})
