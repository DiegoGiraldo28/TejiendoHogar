"""Pruebas de los flujos principales de cuentas."""
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.urls import reverse

from apps.accounts.forms import LoginForm
from apps.accounts.services import registrar_cliente

Usuario = get_user_model()


@pytest.fixture
def cliente(db):
    return Usuario.objects.create_user("ana@example.com", "ClaveFuerte-2026", nombre="Ana")


@pytest.fixture
def emprendedora(db):
    return Usuario.objects.create_superuser("taller@example.com", "ClaveFuerte-2026", nombre="Taller")


def registro_data(**cambios):
    datos = {"nombre": "Luz Tejidos", "correo": "luz@example.com", "password": "ClaveFuerte-2026", "confirmar_password": "ClaveFuerte-2026", "telefono": "300 123 4567", "direccion": "Calle 10", "perfil": "Cliente"}
    return {**datos, **cambios}


@pytest.mark.django_db
def test_manager_normaliza_y_guarda_hash():
    usuario = Usuario.objects.create_user("  ANA@Example.com ", "secreto", nombre="Ana")
    assert usuario.rol == Usuario.Rol.CLIENTE
    assert usuario.correo == "ana@example.com"
    assert usuario.password != "secreto" and usuario.check_password("secreto")
    assert usuario.last_login is None


@pytest.mark.django_db
def test_create_superuser_es_emprendedora():
    usuario = Usuario.objects.create_superuser("taller@example.com", "secreto", nombre="Taller")
    assert usuario.rol == Usuario.Rol.EMPRENDEDORA
    assert usuario.is_active


@pytest.mark.django_db
def test_servicio_registra_solo_cliente():
    usuario = registrar_cliente(**{k: registro_data()[k] for k in ("nombre", "correo", "password", "telefono", "direccion")})
    assert usuario.rol == "Cliente" and usuario.check_password("ClaveFuerte-2026")
    assert usuario.telefono == "300 123 4567"


@pytest.mark.django_db
def test_servicio_rechaza_correo_duplicado_sin_distinguir_mayusculas(cliente):
    with pytest.raises(ValidationError, match="Ya existe"):
        registrar_cliente(nombre="Otra", correo="ANA@EXAMPLE.COM", password="secreto")


@pytest.mark.django_db
def test_servicio_rechaza_telefono_invalido():
    with pytest.raises(ValidationError):
        registrar_cliente(nombre="Otra", correo="otra@example.com", password="ClaveFuerte-2026", telefono="abc")


@pytest.mark.django_db
def test_registro_crea_cliente_y_redirige(client):
    respuesta = client.post(reverse("accounts:registro"), registro_data())
    assert respuesta.status_code == 302 and respuesta.url == reverse("accounts:login")
    assert Usuario.objects.get(correo="luz@example.com").rol == "Cliente"


@pytest.mark.django_db
def test_registro_muestra_errores_de_datos(client, cliente):
    respuesta = client.post(reverse("accounts:registro"), registro_data(correo="ANA@example.com", password="uno", confirmar_password="dos"))
    assert respuesta.status_code == 200
    assert "Ya existe una cuenta" in respuesta.content.decode()
    assert "Las contraseñas no coinciden" in respuesta.content.decode()


@pytest.mark.django_db
def test_registro_emprendedora_se_rechaza_sin_crear(client):
    respuesta = client.post(reverse("accounts:registro"), registro_data(perfil="Emprendedora"))
    assert "Las cuentas de Emprendedora las crea" in respuesta.content.decode()
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_login_coincidente_y_redireccion_por_rol(client, cliente, emprendedora):
    respuesta_cliente = client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "ClaveFuerte-2026", "perfil": "Cliente"})
    assert respuesta_cliente.url == reverse("accounts:cliente")
    client.logout()
    respuesta_taller = client.post(reverse("accounts:login"), {"correo": emprendedora.correo, "password": "ClaveFuerte-2026", "perfil": "Emprendedora"})
    assert respuesta_taller.url == reverse("accounts:emprendedora")


@pytest.mark.django_db
def test_login_credenciales_incorrectas_mensaje_generico(client, cliente):
    respuesta = client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "mala", "perfil": "Cliente"})
    assert "Correo o contraseña incorrectos" in respuesta.content.decode()


@pytest.mark.django_db
def test_selector_no_coincidente_no_autentica(client, cliente):
    respuesta = client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "ClaveFuerte-2026", "perfil": "Emprendedora"})
    assert "Esta cuenta no es de tipo Emprendedora" in respuesta.content.decode()
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_y_registro_redirigen_a_usuario_autenticado(client, cliente):
    client.force_login(cliente)
    assert client.get(reverse("accounts:login")).url == reverse("accounts:cliente")
    assert client.get(reverse("accounts:registro")).url == reverse("accounts:cliente")


@pytest.mark.django_db
def test_logout_solo_post_y_limpia_sesion(client, cliente):
    client.force_login(cliente)
    assert client.get(reverse("accounts:logout")).status_code == 405
    respuesta = client.post(reverse("accounts:logout"))
    assert respuesta.status_code == 302 and respuesta.url == reverse("accounts:login")


@pytest.mark.django_db
def test_recuperacion_no_revela_y_envia_correo(client, cliente):
    respuesta = client.post(reverse("accounts:recuperar"), {"email": cliente.correo})
    assert respuesta.url == reverse("accounts:recuperar_enviado")
    assert len(mail.outbox) == 1
    token_url = re.search(r"/recuperar/[\w-]+/[\w-]+/", mail.outbox[0].body).group(0)
    respuesta_enlace = client.get(token_url, follow=True)
    assert respuesta_enlace.status_code == 200
    ruta_confirmacion = respuesta_enlace.redirect_chain[-1][0]
    respuesta_cambio = client.post(ruta_confirmacion, {"new_password1": "OtraClaveFuerte-2026", "new_password2": "OtraClaveFuerte-2026"})
    assert respuesta_cambio.url == reverse("accounts:recuperar_completo")
    cliente.refresh_from_db()
    assert cliente.check_password("OtraClaveFuerte-2026")
    client.post(reverse("accounts:recuperar"), {"email": "noexiste@example.com"})
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_perfil_actualiza_campos_pero_no_correo(client, cliente):
    client.force_login(cliente)
    respuesta = client.post(reverse("accounts:perfil"), {"nombre": "Ana Nueva", "telefono": "3001234567", "direccion": "Casa 2", "correo": "cambiado@example.com"})
    assert respuesta.url == reverse("accounts:perfil")
    cliente.refresh_from_db()
    assert (cliente.nombre, cliente.telefono, cliente.direccion, cliente.correo) == ("Ana Nueva", "3001234567", "Casa 2", "ana@example.com")


@pytest.mark.django_db
def test_roles_protegen_pantallas_y_anonimo_va_login(client, cliente, emprendedora):
    assert client.get(reverse("accounts:emprendedora")).url.startswith(reverse("accounts:login"))
    client.force_login(cliente)
    assert client.get(reverse("accounts:emprendedora")).status_code == 403
    client.force_login(emprendedora)
    assert client.get(reverse("accounts:cliente")).status_code == 403


@pytest.mark.django_db
def test_raiz_y_paginas_correctas(client, cliente, emprendedora):
    assert client.get("/").url == reverse("accounts:login")
    client.force_login(cliente)
    assert client.get("/").url == reverse("accounts:cliente")
    assert client.get(reverse("accounts:cliente")).status_code == 200
    client.force_login(emprendedora)
    assert client.get("/").url == reverse("accounts:emprendedora")
    assert client.get(reverse("accounts:emprendedora")).status_code == 200


@pytest.mark.django_db
def test_correo_login_se_normaliza(cliente):
    form = LoginForm(data={"correo": "ANA@EXAMPLE.COM", "password": "ClaveFuerte-2026", "perfil": "Cliente"})
    assert form.is_valid()
    assert form.usuario.pk == cliente.pk
