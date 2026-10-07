"""Rutas principales del sitio."""
from django.urls import include, path
from apps.accounts.views import inicio

urlpatterns = [path("", inicio, name="inicio"), path("", include("apps.accounts.urls"))]
