"""Formularios en español para registro, acceso y perfil."""
import logging
from datetime import timedelta

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.common.validators import AYUDA_TELEFONO, PATRON_TELEFONO, validar_telefono
from .models import IntentoAcceso, Usuario

logger = logging.getLogger(__name__)
INTENTOS_MAXIMOS = 5
VENTANA_INTENTOS = timedelta(minutes=15)
MENSAJE_CREDENCIALES = "Correo o contraseña incorrectos."
MENSAJE_BLOQUEO = "Demasiados intentos. Intenta de nuevo en 15 minutos."
AYUDA_CONTRASENA = "Mínimo 8 caracteres, no solo números y no parecida a tu nombre o correo."


class RegistroForm(forms.Form):
    nombre = forms.CharField(
        max_length=150, label="Nombre completo",
        widget=forms.TextInput(attrs={"placeholder": "María Fernanda Gómez", "autocomplete": "name"}),
    )
    correo = forms.EmailField(
        max_length=150, label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com", "autocomplete": "email"}),
    )
    telefono = forms.CharField(
        max_length=20, min_length=7, required=False, label="Teléfono / WhatsApp",
        help_text=AYUDA_TELEFONO,
        widget=forms.TextInput(attrs={
            "type": "tel", "inputmode": "tel", "pattern": PATRON_TELEFONO,
            "placeholder": "+57 310 123 4567", "autocomplete": "tel",
        }),
    )
    password = forms.CharField(
        label="Contraseña", help_text=AYUDA_CONTRASENA,
        widget=forms.PasswordInput(attrs={
            "placeholder": "Mínimo 8 caracteres", "autocomplete": "new-password",
        }),
    )
    confirmar_password = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Repite tu contraseña", "autocomplete": "new-password",
            "data-password-confirm": "",
        }),
    )
    direccion = forms.CharField(max_length=255, required=False, label="Dirección", widget=forms.TextInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            campo.widget.attrs["aria-describedby"] = f"id_{nombre}_help id_{nombre}_errors"

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        validar_telefono(telefono)
        return telefono

    def clean_direccion(self):
        return self.cleaned_data["direccion"].strip()

    def clean(self):
        datos = super().clean()
        if datos.get("password") != datos.get("confirmar_password"):
            self.add_error("confirmar_password", "Las contraseñas no coinciden.")
        return datos

    def clean_password(self):
        password = self.cleaned_data["password"]
        usuario = Usuario(nombre=self.data.get("nombre", ""), correo=self.data.get("correo", ""))
        validate_password(password, user=usuario)
        return password


class LoginForm(forms.Form):
    correo = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com", "autocomplete": "email"}),
    )
    password = forms.CharField(
        label="Contraseña", help_text="Ingresa tu contraseña.",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    usuario = None

    def clean(self):
        datos = super().clean()
        correo, password = datos.get("correo"), datos.get("password")
        if not (correo and password):
            return datos
        correo_normalizado = correo.strip().lower()
        ahora = timezone.now()
        intentos = IntentoAcceso.objects.filter(
            correo=correo_normalizado, exitoso=False, fecha__gte=ahora - VENTANA_INTENTOS,
        ).order_by("fecha")
        if intentos.count() >= INTENTOS_MAXIMOS:
            quinto_intento = intentos[INTENTOS_MAXIMOS - 1]
            if quinto_intento.fecha + VENTANA_INTENTOS > ahora:
                raise ValidationError(MENSAJE_BLOQUEO)
        usuario = authenticate(self.request, username=correo_normalizado, password=password)
        if usuario is None or usuario.rol == Usuario.Rol.OPERARIA:
            IntentoAcceso.objects.create(correo=correo_normalizado, exitoso=False)
            logger.warning("Inicio de sesión fallido para %s a las %s.", correo_normalizado, ahora.isoformat())
            raise ValidationError(MENSAJE_CREDENCIALES)
        IntentoAcceso.objects.filter(correo=correo_normalizado, exitoso=False).delete()
        IntentoAcceso.objects.create(correo=correo_normalizado, exitoso=True)
        self.usuario = usuario
        return datos

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)


class PerfilForm(forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ["nombre", "telefono", "direccion"]
        labels = {"nombre": "Nombre completo", "telefono": "Teléfono", "direccion": "Dirección"}
        widgets = {"telefono": forms.TextInput(attrs={"inputmode": "tel", "pattern": PATRON_TELEFONO,
                   "minlength": "7", "maxlength": "20"}), "direccion": forms.TextInput()}
        help_texts = {"telefono": AYUDA_TELEFONO}

    def clean_telefono(self):
        telefono = (self.cleaned_data.get("telefono") or "").strip()
        validar_telefono(telefono)
        return telefono

    def clean_direccion(self):
        return (self.cleaned_data.get("direccion") or "").strip()


class CorreoRecuperacionForm(PasswordResetForm):
    email = forms.EmailField(
        label="Correo electrónico", widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com"}),
    )


class NuevaContrasenaForm(SetPasswordForm):
    """Presenta en español los campos del restablecimiento de contraseña."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password1"].help_text = AYUDA_CONTRASENA
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        self.fields["new_password2"].help_text = "Escribe nuevamente la contraseña para verificarla."
        for nombre in ("new_password1", "new_password2"):
            self.fields[nombre].widget.attrs.update({
                "autocomplete": "new-password",
                "aria-describedby": f"id_{nombre}_help id_{nombre}_errors",
            })
        self.fields["new_password2"].widget.attrs["data-password-confirm"] = ""
