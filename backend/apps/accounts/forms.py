"""Formularios en español para registro, acceso y perfil."""
import re
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from .models import Usuario


class RegistroForm(forms.Form):
    nombre = forms.CharField(max_length=150, label="Nombre completo", widget=forms.TextInput(attrs={"placeholder": "María Fernanda Gómez", "autocomplete": "name"}))
    correo = forms.EmailField(max_length=150, label="Correo electrónico", widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com", "autocomplete": "email"}))
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono / WhatsApp", widget=forms.TextInput(attrs={"type": "tel", "placeholder": "+57 310 123 4567", "autocomplete": "tel"}))
    password = forms.CharField(label="Contraseña", help_text="Mínimo 8 caracteres, combinando letras y números", widget=forms.PasswordInput(attrs={"data-password-toggle": "", "placeholder": "Mínimo 8 caracteres", "autocomplete": "new-password"}))
    confirmar_password = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput(attrs={"placeholder": "Repite tu contraseña", "autocomplete": "new-password"}))
    direccion = forms.CharField(max_length=255, required=False, label="Dirección", widget=forms.TextInput)
    perfil = forms.ChoiceField(choices=[("Cliente", "Soy Cliente"), ("Emprendedora", "Soy Emprendedora")], initial="Cliente", widget=forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre != "perfil":
                campo.widget.attrs["aria-describedby"] = f"id_{nombre}_help id_{nombre}_errors"

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        if Usuario.objects.filter(correo__iexact=correo).exists():
            raise ValidationError("Ya existe una cuenta con este correo.")
        return correo

    def clean_telefono(self):
        telefono = self.cleaned_data["telefono"].strip()
        if telefono and not re.fullmatch(r"[0-9+ ()-]{7,20}", telefono):
            raise ValidationError("Ingresa un teléfono válido (7 a 20 caracteres).")
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
        validate_password(password, user=Usuario(nombre=self.data.get("nombre", ""), correo=self.data.get("correo", "")))
        return password


class LoginForm(forms.Form):
    correo = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com", "autocomplete": "email"}))
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"data-password-toggle": "", "autocomplete": "current-password"}))
    perfil = forms.ChoiceField(choices=[("Cliente", "Soy Cliente"), ("Emprendedora", "Soy Emprendedora")], initial="Cliente", widget=forms.RadioSelect)
    usuario = None

    def clean(self):
        datos = super().clean()
        correo, password = datos.get("correo"), datos.get("password")
        if correo and password:
            usuario = authenticate(self.request, username=correo.strip().lower(), password=password)
            if usuario is None:
                raise ValidationError("Correo o contraseña incorrectos.")
            if usuario.rol != datos.get("perfil"):
                raise ValidationError(f"Esta cuenta no es de tipo {datos.get('perfil')}.")
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
        widgets = {"telefono": forms.TextInput(), "direccion": forms.TextInput()}

    def clean_telefono(self):
        telefono = (self.cleaned_data.get("telefono") or "").strip()
        if telefono and not re.fullmatch(r"[0-9+ ()-]{7,20}", telefono):
            raise ValidationError("Ingresa un teléfono válido (7 a 20 caracteres).")
        return telefono

    def clean_direccion(self):
        return (self.cleaned_data.get("direccion") or "").strip()


class CorreoRecuperacionForm(PasswordResetForm):
    email = forms.EmailField(label="Correo electrónico", widget=forms.EmailInput(attrs={"placeholder": "tu@correo.com"}))


class NuevaContrasenaForm(SetPasswordForm):
    """Presenta en español los campos del restablecimiento de contraseña."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password1"].help_text = (
            "Usa al menos 8 caracteres, evita datos personales y contraseñas comunes; "
            "combina letras y números."
        )
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        self.fields["new_password2"].help_text = "Escribe nuevamente la contraseña para verificarla."
        for nombre in ("new_password1", "new_password2"):
            self.fields[nombre].widget.attrs.update({
                "data-toggle-password": "",
                "autocomplete": "new-password",
                "aria-describedby": f"id_{nombre}_help id_{nombre}_errors",
            })
