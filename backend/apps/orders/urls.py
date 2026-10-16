"""Rutas provisionales del proceso de pedidos."""
from django.urls import path

from .views import en_proceso

app_name = "orders"
urlpatterns = [path("pedidos/en-proceso/", en_proceso, name="en_proceso")]
