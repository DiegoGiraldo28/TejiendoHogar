"""Vistas delgadas que delegan las reglas de negocio a servicios."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth.views import (
    LoginView, LogoutView, PasswordResetView, PasswordResetDoneView,
    PasswordResetConfirmView, PasswordResetCompleteView,
)
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from apps.common.forms import agregar_errores
from .forms import RegistroForm, LoginForm, PerfilForm, CorreoRecuperacionForm, NuevaContrasenaForm
from .models import Usuario
from .permissions import rol_requerido, RolRequeridoMixin
from .services import registrar_cliente, actualizar_perfil


def destino_rol(usuario):
    """Devuelve el panel activo correspondiente al rol del usuario."""
    return "alerts:panel" if usuario.rol == Usuario.Rol.EMPRENDEDORA else "catalog:lista"


def registro(request):
    """Registra una cuenta pública de Cliente y presenta errores del formulario."""
    if request.user.is_authenticated:
        return redirect(destino_rol(request.user))
    formulario = RegistroForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        try:
            registrar_cliente(**{
                campo: formulario.cleaned_data[campo]
                for campo in ("nombre", "correo", "password", "telefono", "direccion")
            })
        except ValidationError as error:
            agregar_errores(formulario, error)
        else:
            messages.success(request, "Tu cuenta se creó correctamente. Ya puedes iniciar sesión.")
            return redirect("accounts:login")
    return render(request, "accounts/registro.html", {"form": formulario, "auth_tab": "registro"})


class AccesoView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "auth_tab": "login"}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(destino_rol(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        login(self.request, form.usuario)
        # Respeta el retorno seguro solicitado por una acción protegida.
        if self.get_redirect_url():
            return redirect(self.get_success_url())
        return redirect(destino_rol(form.usuario))


class SalirView(LogoutView):
    """Cierra sesión únicamente mediante POST protegido por CSRF."""
    next_page = "accounts:login"


@login_required
def perfil(request):
    """Permite a la persona autenticada actualizar su nombre, teléfono y dirección."""
    formulario = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save(commit=False)
        actualizar_perfil(
            usuario=usuario, nombre=usuario.nombre,
            telefono=usuario.telefono or "", direccion=usuario.direccion or "",
        )
        messages.success(request, "Tu perfil se actualizó correctamente.")
        return redirect("accounts:perfil")
    plantilla = "accounts/perfil.html"
    if request.user.rol == Usuario.Rol.EMPRENDEDORA:
        # Mismo formulario y validaciones; solo cambian las etiquetas y la presentación.
        plantilla = "accounts/perfil_emprendedora.html"
        for nombre, etiqueta in ETIQUETAS_PERFIL_EMPRENDEDORA.items():
            formulario.fields[nombre].label = etiqueta
    return render(request, plantilla, {
        "form": formulario, "iniciales": iniciales(request.user.nombre),
    })


ETIQUETAS_PERFIL_EMPRENDEDORA = {
    "nombre": "Nombre completo",
    "telefono": "Teléfono / WhatsApp de pedidos",
    "direccion": "Dirección de despacho y recolección",
}


def iniciales(nombre: str) -> str:
    """Iniciales del encabezado del perfil: primera letra de las dos primeras palabras («CR»)."""
    palabras = (nombre or "").split()
    return "".join(palabra[0] for palabra in palabras[:2]).upper() or "?"


class RecuperarContrasenaView(PasswordResetView):
    template_name = "accounts/recuperar.html"
    email_template_name = "accounts/recuperar_correo.txt"
    subject_template_name = "accounts/recuperar_asunto.txt"
    form_class = CorreoRecuperacionForm
    success_url = reverse_lazy("accounts:recuperar_enviado")
    from_email = None

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "ses_sandbox": getattr(settings, "SES_SANDBOX", False),
        }


class RecuperarEnviadoView(PasswordResetDoneView):
    template_name = "accounts/recuperar_enviado.html"


class RecuperarConfirmarView(PasswordResetConfirmView):
    template_name = "accounts/recuperar_confirmar.html"
    form_class = NuevaContrasenaForm
    success_url = reverse_lazy("accounts:recuperar_completo")


class RecuperarCompletoView(PasswordResetCompleteView):
    template_name = "accounts/recuperar_completo.html"


@rol_requerido(Usuario.Rol.CLIENTE)
def pagina_cliente(request):
    """Conserva la ruta anterior y lleva al catálogo público."""
    return redirect(destino_rol(request.user))


class PaginaEmprendedoraView(RolRequeridoMixin, View):
    """Conserva la ruta anterior y lleva al panel de gestión."""
    roles_permitidos = (Usuario.Rol.EMPRENDEDORA,)

    def get(self, request):
        return redirect(destino_rol(request.user))
