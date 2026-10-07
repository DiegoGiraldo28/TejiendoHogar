"""Reglas de negocio para las cuentas."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError, transaction

Usuario = get_user_model()


def registrar_cliente(*, nombre, correo, password, telefono="", direccion=""):
    """Crea un Cliente.

    Recibe los datos validados del formulario; devuelve Usuario o lanza
    ValidationError si el correo ya existe o un dato no es válido.
    """
    correo = correo.strip().lower()
    if Usuario.objects.filter(correo__iexact=correo).exists():
        raise ValidationError({"correo": "Ya existe una cuenta con este correo."})
    usuario = Usuario(
        nombre=nombre.strip(), correo=correo, telefono=telefono.strip() or None,
        direccion=direccion.strip() or None, rol=Usuario.Rol.CLIENTE,
    )
    validate_password(password, user=usuario)
    usuario.set_password(password)
    try:
        with transaction.atomic():
            usuario.full_clean(exclude=["password"])
            usuario.save()
    except IntegrityError as error:
        raise ValidationError({"correo": "Ya existe una cuenta con este correo."}) from error
    return usuario


def actualizar_perfil(*, usuario, nombre, telefono="", direccion=""):
    """Actualiza nombre, teléfono y dirección; conserva el correo sin cambios."""
    usuario.nombre = nombre.strip()
    usuario.telefono = telefono.strip() or None
    usuario.direccion = direccion.strip() or None
    usuario.full_clean(exclude=["password"])
    usuario.save(update_fields=["nombre", "telefono", "direccion", "fecha_actualizacion"])
    return usuario
