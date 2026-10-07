"""Formularios en español para registro, acceso y perfil."""
import re
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from .models import Usuario


class RegistroForm(forms.Form):
    nombre = forms.CharField(max_length=150, label="Nombre completo")
    correo = forms.EmailField(max_length=150, label="Correo electrónico")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput(attrs={"data-password-toggle": ""}))
    confirmar_password = forms.CharField(label="Confirmar contraseña", widget=forms.PasswordInput)
    telefono = forms.CharField(max_length=20, required=False, label="Teléfono")
    direccion = forms.CharField(max_length=255, required=False, label="Dirección", widget=forms.TextInput)
    perfil = forms.ChoiceField(choices=[("Cliente", "Soy Cliente"), ("Emprendedora", "Soy Emprendedora")], initial="Cliente", widget=forms.RadioSelect)

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
