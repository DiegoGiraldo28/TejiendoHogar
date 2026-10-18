"""Páginas estáticas de información legal."""
from django.shortcuts import render


def terminos(request):
    """Muestra las condiciones generales de uso y compra."""
    return render(request, "legal/terminos.html")


def privacidad(request):
    """Muestra la política de tratamiento de datos personales."""
    return render(request, "legal/privacidad.html")


def cookies(request):
    """Informa sobre las cookies estrictamente necesarias."""
    return render(request, "legal/cookies.html")
