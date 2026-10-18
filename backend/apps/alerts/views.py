"""Panel resumido para la emprendedora."""
from datetime import timedelta

from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.accounts.permissions import rol_requerido
from apps.catalog.models import Producto
from apps.inventory.services import insumos_en_stock_bajo, productos_en_stock_bajo, unidades_fabricables


@rol_requerido(Usuario.Rol.EMPRENDEDORA)
def panel(request):
    """Muestra conteos de catálogo, stock bajo y capacidad por receta."""
    total_productos = Producto.objects.count()
    limite_actividad = timezone.now() - timedelta(days=30)
    sin_actividad = Producto.objects.filter(fecha_actualizacion__lte=limite_actividad).count()
    porcentaje_sin_actividad = round(sin_actividad * 100 / total_productos) if total_productos else 0
    sobre_pedido = Producto.objects.filter(
        tipo=Producto.Tipo.SOBRE_PEDIDO, activo=True,
    ).annotate(receta_count=Count("receta", distinct=True)).order_by("nombre")
    fabricables = [
        {"producto": producto, "unidades": unidades_fabricables(producto=producto)}
        for producto in sobre_pedido
    ]
    return render(request, "alerts/panel.html", {
        "user_nombre": request.user.nombre,
        "productos_activos": Producto.objects.filter(activo=True).count(),
        "porcentaje_sin_actividad": porcentaje_sin_actividad,
        "insumos_bajos": insumos_en_stock_bajo(),
        "productos_bajos": productos_en_stock_bajo(),
        "productos_fabricables": fabricables,
    })
