"""Rutas del proceso de pedidos."""
from django.urls import path
from django.views.generic import RedirectView

from . import views, views_emprendedora

app_name = "orders"
urlpatterns = [
    path("emprendedora/pedidos/", views_emprendedora.gestion_pedidos, name="gestion"),
    path("emprendedora/pedidos/<int:pedido_id>/", views_emprendedora.gestion_pedido, name="gestion_pedido"),
    path("emprendedora/pedidos/<int:pedido_id>/avanzar/", views_emprendedora.avanzar_pedido, name="avanzar"),
    path("emprendedora/pedidos/<int:pedido_id>/cancelar/", views_emprendedora.cancelar_pedido_gestion,
         name="gestion_cancelar"),
    path("carrito/", views.bolsa, name="bolsa"),
    path("carrito/agregar/<int:producto_id>/", views.bolsa_agregar, name="bolsa_agregar"),
    path("pedidos/<int:pedido_id>/pago/", views.pago, name="pago"),
    path("mis-pedidos/", views.mis_pedidos, name="mis_pedidos"),
    path("mis-pedidos/<int:pedido_id>/", views.seguimiento, name="seguimiento"),
    path("mis-pedidos/<int:pedido_id>/cancelar/", views.cancelar, name="cancelar"),
    # La página provisional «Pedido en proceso» se retiró: la ruta vieja lleva a la bolsa.
    path("pedidos/en-proceso/", RedirectView.as_view(pattern_name="orders:bolsa"), name="en_proceso"),
]
