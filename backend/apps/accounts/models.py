"""Modelo de usuario mapeado a la tabla definida por el esquema."""
import re

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models


class UsuarioManager(BaseUserManager):
    """Crea usuarios finales y la cuenta de administración del taller."""

    def create_user(self, correo, password=None, **extra_fields):
        correo = self.normalize_email(correo).lower()
        extra_fields.setdefault("rol", self.model.Rol.CLIENTE)
        usuario = self.model(correo=correo, **extra_fields)
        usuario.set_password(password)
        usuario.full_clean(exclude=["password"])
        usuario.save(using=self._db)
        return usuario

    def create_superuser(self, correo, password=None, **extra_fields):
        extra_fields.setdefault("nombre", correo)
        extra_fields["rol"] = Usuario.Rol.EMPRENDEDORA
        extra_fields["is_active"] = True
        return self.create_user(correo, password, **extra_fields)


class Usuario(AbstractBaseUser):
    """Cuenta de acceso para Cliente, Emprendedora u Operaria."""

    class Rol(models.TextChoices):
        EMPRENDEDORA = "Emprendedora", "Emprendedora"
        CLIENTE = "Cliente", "Cliente"
        OPERARIA = "Operaria", "Operaria"

    id_usuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)
    correo = models.EmailField(max_length=150)
    password = models.CharField(max_length=255, db_column="contrasena_hash")
    telefono = models.CharField(max_length=20, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    rol = models.CharField(max_length=20, choices=Rol.choices)
    is_active = models.BooleanField(default=True, db_column="activo")
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    last_login = None

    objects = UsuarioManager()
    USERNAME_FIELD = "correo"
    EMAIL_FIELD = "correo"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        db_table = "usuario"
        indexes = [models.Index(fields=["rol"], name="idx_usuario_rol"), models.Index(fields=["is_active"], name="idx_usuario_activo")]
        constraints = [
            models.UniqueConstraint(fields=["correo"], name="uq_usuario_correo"),
            models.CheckConstraint(condition=models.Q(rol__in=["Emprendedora", "Cliente", "Operaria"]), name="ck_usuario_rol"),
            models.CheckConstraint(condition=models.Q(telefono__isnull=True) | models.Q(telefono__regex=r"^[0-9+ ()-]{7,20}$"), name="ck_usuario_telefono"),
            models.CheckConstraint(condition=models.Q(direccion__isnull=True) | ~models.Q(direccion=""), name="ck_usuario_direccion"),
        ]

    def clean(self):
        super().clean()
        if self.correo:
            self.correo = self.correo.strip().lower()
        if self.telefono and not re.fullmatch(r"[0-9+ ()-]{7,20}", self.telefono):
            raise ValidationError({"telefono": "Ingresa un teléfono válido (7 a 20 caracteres)."})
        if self.direccion == "":
            raise ValidationError({"direccion": "La dirección no puede estar vacía."})

    def __str__(self):
        return self.correo
