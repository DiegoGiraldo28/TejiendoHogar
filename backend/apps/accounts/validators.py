"""Validadores de contraseña del proyecto."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class LetrasYNumerosValidator:
    """Exige al menos una letra y un número en la contraseña."""

    def validate(self, password, user=None):
        """Valida la mezcla de caracteres y lanza ValidationError si falta."""
        tiene_letra = any(caracter.isalpha() for caracter in password)
        tiene_numero = any(caracter.isdigit() for caracter in password)
        if not (tiene_letra and tiene_numero):
            raise ValidationError(
                _("La contraseña debe combinar al menos una letra y un número."),
                code="password_letter_and_number",
            )

    def get_help_text(self):
        """Devuelve una explicación breve para el formulario de contraseña."""
        return _("La contraseña debe combinar al menos una letra y un número.")
