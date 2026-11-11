"""Pruebas de los flujos principales de cuentas."""
import re

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounts.forms import LoginForm
from apps.accounts.models import IntentoAcceso
from apps.accounts.services import registrar_cliente
from django.test import Client
from django.test import override_settings

Usuario = get_user_model()


def registro_data(**cambios):
    datos = {
        "nombre": "Luz Tejidos", "correo": "luz@example.com", "password": "ClaveFuerte-2026",
        "confirmar_password": "ClaveFuerte-2026", "telefono": "300 123 4567", "direccion": "Calle 10",
    }
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
    campos = ("nombre", "correo", "password", "telefono", "direccion")
    usuario = registrar_cliente(**{campo: registro_data()[campo] for campo in campos})
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
    usuario = Usuario.objects.get(correo="luz@example.com")
    assert usuario.rol == "Cliente"
    assert usuario.direccion == "Calle 10"


@pytest.mark.django_db
def test_registro_muestra_ayudas_y_atributos_de_validacion(client):
    respuesta = client.get(reverse("accounts:registro"))
    contenido = respuesta.content.decode()
    posiciones = [contenido.index(f'name="{nombre}"') for nombre in (
        "nombre", "correo", "telefono", "password", "confirmar_password",
    )]

    assert posiciones == sorted(posiciones)
    assert 'inputmode="tel"' in contenido
    assert 'minlength="7"' in contenido and 'maxlength="20"' in contenido
    assert 'pattern="[0-9+ ()-]{7,20}"' in contenido
    assert "Entre 7 y 20 caracteres: números, espacios, +, - o paréntesis" in contenido
    assert "Mínimo 8 caracteres, no solo números y no parecida a tu nombre o correo" in contenido
    assert "Términos y condiciones" in contenido and "Política de Privacidad" in contenido
    assert "100% PROTEGIDA" in contenido


@pytest.mark.django_db
def test_registro_muestra_errores_de_datos(client, cliente):
    respuesta = client.post(reverse("accounts:registro"), registro_data(
        correo="ANA@example.com", password="uno", confirmar_password="dos",
    ))
    assert respuesta.status_code == 200
    assert "Ya existe una cuenta" in respuesta.content.decode()
    assert "Las contraseñas no coinciden" in respuesta.content.decode()


@pytest.mark.django_db
def test_registro_no_muestra_selector_y_crea_cliente(client):
    from apps.accounts.forms import RegistroForm

    assert "perfil" not in RegistroForm().fields
    respuesta = client.post(reverse("accounts:registro"), registro_data())
    assert respuesta.status_code == 302
    assert Usuario.objects.get(correo="luz@example.com").rol == Usuario.Rol.CLIENTE


@pytest.mark.django_db
def test_registro_ignora_perfil_enviado_por_post(client):
    respuesta = client.post(reverse("accounts:registro"), registro_data(perfil="Emprendedora"))
    assert respuesta.status_code == 302
    assert Usuario.objects.get(correo="luz@example.com").rol == Usuario.Rol.CLIENTE


@pytest.mark.django_db
def test_registro_rechaza_telefono_invalido_enviado_por_post(client):
    respuesta = client.post(reverse("accounts:registro"), registro_data(
        correo="telefono@example.com", telefono="123abc4"))
    assert respuesta.status_code == 200
    assert "Ingresa un teléfono válido" in respuesta.content.decode()


@pytest.mark.parametrize("password", ["soloLetras", "12345678"])
@pytest.mark.django_db
def test_registro_exige_letras_y_numeros(client, password):
    respuesta = client.post(reverse("accounts:registro"), registro_data(
        password=password, confirmar_password=password,
    ))
    assert respuesta.status_code == 200
    assert "combinar al menos una letra y un número" in respuesta.content.decode()
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_login_coincidente_y_redireccion_por_rol(client, cliente, emprendedora):
    respuesta_cliente = client.post(reverse("accounts:login"), {
        "correo": cliente.correo, "password": "ClaveFuerte-2026",
    })
    assert respuesta_cliente.url == reverse("catalog:lista")
    client.logout()
    respuesta_taller = client.post(reverse("accounts:login"), {
        "correo": emprendedora.correo, "password": "ClaveFuerte-2026",
    })
    assert respuesta_taller.url == reverse("alerts:panel")


@pytest.mark.django_db
def test_login_credenciales_incorrectas_mensaje_generico(client, cliente):
    respuesta = client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "mala"})
    assert "Correo o contraseña incorrectos" in respuesta.content.decode()


@pytest.mark.django_db
def test_rol_sin_acceso_web_usa_mensaje_generico_y_no_autentica(client, db):
    usuario = Usuario.objects.create_user(
        "operaria@example.com", "ClaveFuerte-2026", nombre="Operaria", rol=Usuario.Rol.OPERARIA,
    )
    respuesta = client.post(reverse("accounts:login"), {"correo": usuario.correo, "password": "ClaveFuerte-2026"})
    assert "Correo o contraseña incorrectos." in respuesta.content.decode()
    assert "_auth_user_id" not in client.session
    assert not IntentoAcceso.objects.get(correo=usuario.correo).exitoso


@pytest.mark.django_db
def test_login_bloquea_al_quinto_fallo_y_el_bloqueo_expira(client):
    for _ in range(5):
        respuesta = client.post(reverse("accounts:login"), {
            "correo": "fallos@example.com", "password": "incorrecta",
        })
        assert "Correo o contraseña incorrectos." in respuesta.content.decode()
    assert IntentoAcceso.objects.filter(correo="fallos@example.com", exitoso=False).count() == 5

    bloqueada = client.post(reverse("accounts:login"), {
        "correo": "fallos@example.com", "password": "incorrecta",
    })
    assert "Demasiados intentos. Intenta de nuevo en 15 minutos." in bloqueada.content.decode()

    IntentoAcceso.objects.filter(correo="fallos@example.com").update(
        fecha=timezone.now() - timedelta(minutes=16))
    expirada = client.post(reverse("accounts:login"), {
        "correo": "fallos@example.com", "password": "incorrecta",
    })
    assert "Correo o contraseña incorrectos." in expirada.content.decode()


@pytest.mark.django_db
def test_login_exitoso_reinicia_el_conteo_de_intentos(client, cliente):
    for _ in range(4):
        client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "incorrecta"})
    correcto = client.post(reverse("accounts:login"), {
        "correo": cliente.correo, "password": "ClaveFuerte-2026",
    })
    assert correcto.url == reverse("catalog:lista")
    assert IntentoAcceso.objects.filter(correo=cliente.correo, exitoso=False).count() == 0
    assert IntentoAcceso.objects.filter(correo=cliente.correo, exitoso=True).count() == 1
    client.logout()
    client.post(reverse("accounts:login"), {"correo": cliente.correo, "password": "incorrecta"})
    assert IntentoAcceso.objects.filter(correo=cliente.correo, exitoso=False).count() == 1


@pytest.mark.parametrize("nombre,correo,password", [
    ("Luz Tejidos", "luz@example.com", "luz@example.com"),
    ("Luz Tejidos", "luz@example.com", "LuzTejidos2026"),
])
@pytest.mark.django_db
def test_registro_rechaza_contrasena_similar_a_nombre_o_correo(nombre, correo, password):
    with pytest.raises(ValidationError):
        registrar_cliente(nombre=nombre, correo=correo, password=password)


@pytest.mark.django_db
def test_login_y_registro_redirigen_a_usuario_autenticado(client, cliente):
    client.force_login(cliente)
    assert client.get(reverse("accounts:login")).url == reverse("catalog:lista")
    assert client.get(reverse("accounts:registro")).url == reverse("catalog:lista")


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
    respuesta_cambio = client.post(ruta_confirmacion, {
        "new_password1": "OtraClaveFuerte-2026", "new_password2": "OtraClaveFuerte-2026",
    })
    assert respuesta_cambio.url == reverse("accounts:recuperar_completo")
    cliente.refresh_from_db()
    assert cliente.check_password("OtraClaveFuerte-2026")
    client.post(reverse("accounts:recuperar"), {"email": "noexiste@example.com"})
    assert len(mail.outbox) == 1


@override_settings(SES_SANDBOX=True)
def test_aviso_ses_sandbox_visible_con_enlace_mailto(client):
    respuesta = client.get(reverse("accounts:recuperar"))

    contenido = respuesta.content.decode()
    assert "Por ahora, el correo de recuperación solo llega a direcciones previamente verificadas." in contenido
    assert '<a href="mailto:diegoh.giraldoc@uqvirtual.edu.co">' in contenido


@override_settings(SES_SANDBOX=False)
def test_aviso_ses_sandbox_oculto_con_ajuste_falso(client):
    respuesta = client.get(reverse("accounts:recuperar"))

    assert "Por ahora, el correo de recuperación" not in respuesta.content.decode()


def test_aviso_ses_sandbox_oculto_si_ajuste_no_existe(client):
    respuesta = client.get(reverse("accounts:recuperar"))

    assert "Por ahora, el correo de recuperación" not in respuesta.content.decode()


@pytest.mark.django_db
def test_perfil_actualiza_campos_pero_no_correo(client, cliente):
    client.force_login(cliente)
    respuesta = client.post(reverse("accounts:perfil"), {
        "nombre": "Ana Nueva", "telefono": "3001234567", "direccion": "Casa 2",
        "correo": "cambiado@example.com",
    })
    assert respuesta.url == reverse("accounts:perfil")
    cliente.refresh_from_db()
    assert (cliente.nombre, cliente.telefono, cliente.direccion, cliente.correo) == (
        "Ana Nueva", "3001234567", "Casa 2", "ana@example.com",
    )


@pytest.mark.django_db
def test_roles_protegen_pantallas_y_anonimo_va_login(client, cliente, emprendedora):
    assert client.get(reverse("accounts:emprendedora")).url.startswith(reverse("accounts:login"))
    client.force_login(cliente)
    assert client.get(reverse("accounts:emprendedora")).status_code == 403
    client.force_login(emprendedora)
    assert client.get(reverse("accounts:cliente")).status_code == 403


@pytest.mark.django_db
def test_raiz_y_paginas_correctas(client, cliente, emprendedora):
    respuesta_anonima = client.get("/")
    assert respuesta_anonima.status_code == 200
    assert any(template.name == "inicio.html" for template in respuesta_anonima.templates)
    client.force_login(cliente)
    assert client.get("/").url == reverse("catalog:lista")
    respuesta_cliente = client.get(reverse("accounts:cliente"))
    assert respuesta_cliente.status_code == 302 and respuesta_cliente.url == reverse("catalog:lista")
    client.force_login(emprendedora)
    assert client.get("/").url == reverse("alerts:panel")
    respuesta_emprendedora = client.get(reverse("accounts:emprendedora"))
    assert respuesta_emprendedora.status_code == 302 and respuesta_emprendedora.url == reverse("alerts:panel")


@pytest.mark.django_db
def test_correo_login_se_normaliza(cliente):
    form = LoginForm(data={"correo": "ANA@EXAMPLE.COM", "password": "ClaveFuerte-2026"})
    assert form.is_valid()
    assert form.usuario.pk == cliente.pk


@pytest.mark.django_db
def test_contrasena_se_guarda_con_pbkdf2(cliente):
    assert cliente.password.startswith("pbkdf2_sha256$")


@pytest.mark.django_db
def test_login_sin_token_csrf_es_rechazado(cliente):
    navegador = Client(enforce_csrf_checks=True)
    respuesta = navegador.post(reverse("accounts:login"), {
        "correo": cliente.correo, "password": "ClaveFuerte-2026",
    })
    assert respuesta.status_code == 403


@pytest.mark.django_db
def test_perfil_cliente_muestra_encabezado_secciones_y_mismos_campos(client, cliente):
    usuaria = cliente
    usuaria.nombre = "Camila Restrepo"
    usuaria.save(update_fields=["nombre"])
    client.force_login(usuaria)
    respuesta = client.get(reverse("accounts:perfil"))
    contenido = respuesta.content.decode()
    assert respuesta.context["iniciales"] == "CR"
    assert '<span class="perfil-iniciales" aria-hidden="true">CR</span>' in contenido
    assert f'<p class="perfil-correo">{usuaria.correo}</p>' in contenido
    assert usuaria.get_rol_display() in contenido.split('class="perfil-rol"')[1].split("</span>")[0]
    assert "Información personal" in contenido and "Dirección de entrega" in contenido
    assert list(respuesta.context["form"].fields) == ["nombre", "telefono", "direccion"]
    assert 'id="correo" type="email"' in contenido and "readonly" in contenido
    assert 'inputmode="tel"' in contenido and 'pattern="' in contenido
    assert "Guardar cambios" in contenido and "Cerrar sesión" in contenido
    assert "Mi perfil y taller" not in contenido and "Piezas entregadas" not in contenido
    for omitido in ("Cédula", "Ciudad", "Barrio", "Notas para entrega"):
        assert omitido not in contenido


@pytest.mark.django_db
def test_perfil_emprendedora_muestra_identidad_y_datos_sin_entregas(client, emprendedora):
    emprendedora.nombre = "María José Taller"
    emprendedora.save(update_fields=["nombre"])
    client.force_login(emprendedora)
    respuesta = client.get(reverse("accounts:perfil"))
    contenido = respuesta.content.decode()
    assert [t.name for t in respuesta.templates][0] == "accounts/perfil_emprendedora.html"
    assert "Configuración general" in contenido and "<h1>Mi perfil y taller</h1>" in contenido
    assert "Gestiona tu información de contacto con tus clientas." in contenido
    assert '<span class="perfil-taller-avatar" aria-hidden="true">MJ</span>' in contenido
    assert '<span class="perfil-taller-rol">Emprendedora</span>' in contenido
    assert f"<dd>{emprendedora.fecha_registro:%Y}</dd>" in contenido
    assert re.search(r"Piezas entregadas</dt>\s*<dd>0</dd>", contenido)
    assert "Editar información básica" in contenido
    for etiqueta in ("Nombre completo", "Correo electrónico de contacto", "Teléfono / WhatsApp de pedidos",
                     "Dirección de despacho y recolección"):
        assert etiqueta in contenido
    assert 'inputmode="tel"' in contenido and 'pattern="' in contenido and "readonly" in contenido
    assert f'href="{reverse("alerts:panel")}">Cancelar</a>' in contenido and ">Guardar</button>" in contenido
    assert "Cerrar sesión" not in contenido and ">Salir<" in contenido
    for omitido in ("Artesana certificada", "Verificado", "Recepción de pagos", "Historia del taller"):
        assert omitido not in contenido


@pytest.mark.django_db
def test_perfil_emprendedora_guarda_cambios_y_valida_telefono(client, emprendedora):
    client.force_login(emprendedora)
    url = reverse("accounts:perfil")
    invalido = client.post(url, {"nombre": "Taller", "telefono": "abc", "direccion": "Carrera 1"})
    assert invalido.status_code == 200 and invalido.context["form"].errors["telefono"]
    assert "Revisa los campos marcados." in invalido.content.decode()
    assert 'id="id_telefono_errors"' in invalido.content.decode()
    respuesta = client.post(url, {"nombre": "Taller Tunja", "telefono": "3109876543", "direccion": "Calle 5 # 2-10"})
    assert respuesta.url == url
    emprendedora.refresh_from_db()
    assert (emprendedora.nombre, emprendedora.telefono, emprendedora.direccion) == (
        "Taller Tunja", "3109876543", "Calle 5 # 2-10",
    )


@pytest.mark.django_db
def test_perfil_muestra_errores_de_telefono_junto_al_campo(client, cliente):
    client.force_login(cliente)
    respuesta = client.post(reverse("accounts:perfil"), {"nombre": "Ana", "telefono": "abc", "direccion": ""})
    assert respuesta.status_code == 200
    assert respuesta.context["form"].errors["telefono"]
    assert "Revisa los campos marcados." in respuesta.content.decode()


@pytest.mark.django_db
def test_emprendedora_ve_icono_de_perfil_y_salir(client, emprendedora):
    client.force_login(emprendedora)
    panel = client.get(reverse("alerts:panel")).content.decode()
    assert f'<a class="icono-nav" href="{reverse("accounts:perfil")}" aria-label="Mi perfil"' in panel
    assert ">Mi perfil</a>" not in panel and ">Salir<" in panel
    perfil = client.get(reverse("accounts:perfil")).content.decode()
    assert 'aria-label="Mi perfil" aria-current="page"' in perfil
