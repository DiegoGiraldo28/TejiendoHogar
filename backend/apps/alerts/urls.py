"""Rutas del panel del taller."""
from django.urls import path

from .views import panel

app_name = "alerts"
urlpatterns = [path("panel/", panel, name="panel")]
