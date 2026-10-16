"""Vistas de gestión de insumos, movimientos y receta."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.catalog.models import Producto
from .forms import EntradaForm, InsumoEdicionForm, InsumoForm, MovimientoFiltroForm, RecetaFormSet
from .models import Insumo, MovimientoInsumo
from .services import actualizar_insumo, crear_insumo, eliminar_insumo, guardar_receta, registrar_entrada


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def lista_insumos(request):
    insumos = Insumo.objects.order_by("nombre")
    busqueda = request.GET.get("q", "").strip()
    if busqueda:
        insumos = insumos.filter(nombre__icontains=busqueda)
    pagina = Paginator(insumos, 12).get_page(request.GET.get("page"))
    return render(request, "inventory/insumos.html", {"pagina": pagina})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def insumo_nuevo(request):
    formulario = InsumoForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            crear_insumo(**formulario.cleaned_data)
        except ValidationError as error:
            _agregar_errores(formulario, error)
        else:
            messages.success(request, "Materia prima registrada correctamente.")
            return redirect("inventory:insumos")
    return render(request, "inventory/insumo_form.html", {"form": formulario, "titulo": "Registrar material"})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def insumo_editar(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    formulario = InsumoEdicionForm(request.POST or None, instance=insumo)
    if request.method == "POST" and formulario.is_valid():
        try:
            actualizar_insumo(insumo=insumo, **formulario.cleaned_data)
        except ValidationError as error:
            _agregar_errores(formulario, error)
        else:
            messages.success(request, "Datos del insumo actualizados.")
            return redirect("inventory:insumos")
    return render(request, "inventory/insumo_form.html", {"form": formulario, "titulo": "Actualizar material", "insumo": insumo})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def insumo_entrada(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    formulario = EntradaForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            registrar_entrada(insumo_id=insumo.pk, cantidad=formulario.cleaned_data["cantidad"])
        except ValidationError as error:
            _agregar_errores(formulario, error)
        else:
            messages.success(request, "Entrada de inventario registrada correctamente.")
            return redirect("inventory:insumo_movimientos", insumo_id=insumo.pk)
    return render(request, "inventory/insumo_entrada.html", {"form": formulario, "insumo": insumo})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def insumo_movimientos(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    formulario = MovimientoFiltroForm(request.GET or None)
    movimientos = MovimientoInsumo.objects.filter(insumo=insumo).order_by("-fecha_movimiento", "-pk")
    if formulario.is_valid() and formulario.cleaned_data["tipo_movimiento"]:
        movimientos = movimientos.filter(tipo_movimiento=formulario.cleaned_data["tipo_movimiento"])
    pagina = Paginator(movimientos, 20).get_page(request.GET.get("page"))
    return render(request, "inventory/movimientos.html", {"insumo": insumo, "form": formulario, "pagina": pagina})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def insumo_eliminar(request, insumo_id):
    insumo = get_object_or_404(Insumo, pk=insumo_id)
    if request.method == "POST":
        try:
            eliminar_insumo(insumo=insumo)
        except ValidationError as error:
            for mensajes_error in error.message_dict.values():
                for mensaje in mensajes_error:
                    messages.error(request, mensaje)
        else:
            messages.success(request, "Insumo eliminado correctamente.")
        return redirect("inventory:insumos")
    return render(request, "inventory/insumo_confirmar_eliminar.html", {"insumo": insumo})


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def receta(request, producto_id):
    producto = get_object_or_404(Producto, pk=producto_id)
    formset = RecetaFormSet(request.POST or None, instance=producto, prefix="receta")
    if request.method == "POST" and formset.is_valid():
        try:
            guardar_receta(producto=producto, lineas=[form.cleaned_data for form in formset.forms])
        except ValidationError as error:
            for mensajes_error in error.message_dict.values():
                for mensaje in mensajes_error:
                    formset.forms[0].add_error(None, mensaje)
        else:
            messages.success(request, "Receta guardada. Puedes activarla desde la lista de productos.")
            return redirect("inventory:receta", producto_id=producto.pk)
    return render(request, "inventory/receta.html", {"producto": producto, "formset": formset})


def _agregar_errores(formulario, error):
    if hasattr(error, "message_dict"):
        for campo, errores in error.message_dict.items():
            for mensaje in errores:
                formulario.add_error(campo if campo in formulario.fields else None, mensaje)
    else:
        formulario.add_error(None, str(error))
