"""Rutas principales del sitio."""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from apps.accounts.views import inicio

urlpatterns = [
    path("", inicio, name="inicio"),
    path("", include("apps.accounts.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.alerts.urls")),
    path("", include("apps.orders.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
