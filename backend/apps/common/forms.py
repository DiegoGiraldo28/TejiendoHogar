"""Ayudantes compartidos para adaptar errores de dominio a formularios."""


def agregar_errores(formulario, error) -> None:
    """Copia los errores de un ValidationError al formulario correspondiente."""
    if hasattr(error, "message_dict"):
        for campo, errores in error.message_dict.items():
            for mensaje in errores:
                formulario.add_error(campo if campo in formulario.fields else None, mensaje)
    else:
        for mensaje in error.messages:
            formulario.add_error(None, mensaje)
