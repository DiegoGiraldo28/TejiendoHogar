"""Rutas del proceso de cuentas."""
from django.urls import path, re_path
from . import views

app_name = "accounts"
urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("login/", views.AccesoView.as_view(), name="login"),
    path("logout/", views.SalirView.as_view(), name="logout"),
    path("recuperar/", views.RecuperarContrasenaView.as_view(), name="recuperar"),
    path("recuperar/enviado/", views.RecuperarEnviadoView.as_view(), name="recuperar_enviado"),
    re_path(r"^recuperar/(?P<uidb64>[0-9A-Za-z_-]+)/(?P<token>[^/]+)/$", views.RecuperarConfirmarView.as_view(), name="recuperar_confirmar"),
    path("recuperar/completo/", views.RecuperarCompletoView.as_view(), name="recuperar_completo"),
    path("perfil/", views.perfil, name="perfil"),
    path("cliente/", views.pagina_cliente, name="cliente"),
    path("emprendedora/", views.PaginaEmprendedoraView.as_view(), name="emprendedora"),
]
