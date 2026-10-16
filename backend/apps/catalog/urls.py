"""Rutas de productos."""
from django.urls import path

from . import views

app_name = "catalog"
urlpatterns = [
    path("catalogo/", views.lista, name="lista"),
    path("catalogo/<int:producto_id>/", views.detalle, name="detalle"),
    path("emprendedora/productos/", views.lista_productos, name="productos"),
    path("emprendedora/productos/nuevo/", views.producto_nuevo, name="producto_nuevo"),
    path("emprendedora/productos/<int:producto_id>/editar/", views.producto_editar, name="producto_editar"),
    path("emprendedora/productos/<int:producto_id>/estado/", views.producto_estado, name="producto_estado"),
    path("emprendedora/productos/<int:producto_id>/eliminar/", views.producto_eliminar, name="producto_eliminar"),
]
