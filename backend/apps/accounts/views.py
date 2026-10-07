"""Vistas delgadas que delegan las reglas de negocio a servicios."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .forms import RegistroForm, LoginForm, PerfilForm, CorreoRecuperacionForm
from .models import Usuario
from .permissions import rol_requerido, RolRequeridoMixin
from .services import registrar_cliente, actualizar_perfil


def destino_rol(usuario):
    """Devuelve el panel provisional correspondiente al rol."""
    return "accounts:emprendedora" if usuario.rol == Usuario.Rol.EMPRENDEDORA else "accounts:cliente"


def registro(request):
    if request.user.is_authenticated:
        return redirect(destino_rol(request.user))
    formulario = RegistroForm(request.POST or None)
    if request.method == "POST" and formulario.is_valid():
        if formulario.cleaned_data["perfil"] == Usuario.Rol.EMPRENDEDORA:
            formulario.add_error("perfil", "Las cuentas de Emprendedora las crea el administrador del sistema.")
        else:
            try:
                registrar_cliente(**{campo: formulario.cleaned_data[campo] for campo in ("nombre", "correo", "password", "telefono", "direccion")})
            except ValidationError as error:
                for campo, errores in error.message_dict.items():
                    for mensaje in errores:
                        formulario.add_error(campo, mensaje)
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
        return redirect(destino_rol(form.usuario))


class SalirView(LogoutView):
    """Cierra sesión únicamente mediante POST protegido por CSRF."""
    next_page = "accounts:login"


@login_required
def perfil(request):
    formulario = PerfilForm(request.POST or None, instance=request.user)
    if request.method == "POST" and formulario.is_valid():
        usuario = formulario.save(commit=False)
        actualizar_perfil(usuario=usuario, nombre=usuario.nombre, telefono=usuario.telefono or "", direccion=usuario.direccion or "")
        messages.success(request, "Tu perfil se actualizó correctamente.")
        return redirect("accounts:perfil")
    return render(request, "accounts/perfil.html", {"form": formulario})


class RecuperarContrasenaView(PasswordResetView):
    template_name = "accounts/recuperar.html"
    email_template_name = "accounts/recuperar_correo.txt"
    subject_template_name = "accounts/recuperar_asunto.txt"
    form_class = CorreoRecuperacionForm
    success_url = reverse_lazy("accounts:recuperar_enviado")
    from_email = None


class RecuperarEnviadoView(PasswordResetDoneView):
    template_name = "accounts/recuperar_enviado.html"


class RecuperarConfirmarView(PasswordResetConfirmView):
    template_name = "accounts/recuperar_confirmar.html"
    success_url = reverse_lazy("accounts:recuperar_completo")


class RecuperarCompletoView(PasswordResetCompleteView):
    template_name = "accounts/recuperar_completo.html"


@rol_requerido(Usuario.Rol.CLIENTE)
def pagina_cliente(request):
    """Página provisional del cliente; TODO: será reemplazada por el catálogo."""
    return render(request, "accounts/cliente.html")


class PaginaEmprendedoraView(RolRequeridoMixin, View):
    """Página provisional; TODO: será reemplazada por el panel de taller."""
    roles_permitidos = (Usuario.Rol.EMPRENDEDORA,)

    def get(self, request):
        return render(request, "accounts/emprendedora.html")


def inicio(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    return redirect(destino_rol(request.user))
