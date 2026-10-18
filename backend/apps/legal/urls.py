"""Rutas de información legal."""
from django.urls import path

from . import views

app_name = "legal"
urlpatterns = [
    path("terminos-y-condiciones/", views.terminos, name="terminos"),
    path("politica-de-privacidad/", views.privacidad, name="privacidad"),
    path("politica-de-cookies/", views.cookies, name="cookies"),
]
