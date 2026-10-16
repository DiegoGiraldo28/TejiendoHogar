"""Rutas de materias primas y recetas."""
from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("emprendedora/insumos/", views.lista_insumos, name="insumos"),
    path("emprendedora/insumos/nuevo/", views.insumo_nuevo, name="insumo_nuevo"),
    path("emprendedora/insumos/<int:insumo_id>/editar/", views.insumo_editar, name="insumo_editar"),
    path("emprendedora/insumos/<int:insumo_id>/entrada/", views.insumo_entrada, name="insumo_entrada"),
    path("emprendedora/insumos/<int:insumo_id>/movimientos/", views.insumo_movimientos, name="insumo_movimientos"),
    path("emprendedora/insumos/<int:insumo_id>/eliminar/", views.insumo_eliminar, name="insumo_eliminar"),
    path("emprendedora/productos/<int:producto_id>/receta/", views.receta, name="receta"),
]
