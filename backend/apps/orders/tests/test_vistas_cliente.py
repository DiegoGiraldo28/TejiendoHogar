"""Pruebas funcionales de la Cliente: bolsa, pago simulado, Mis pedidos y seguimiento."""
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.catalog.models import Producto
from apps.inventory.models import Insumo
from apps.orders.models import Pedido, RechazoPedido
from apps.orders.services import PedidoYaConfirmado, crear_pedido
from .ayudantes import DIRECCION, TELEFONO, disponible, otra_cliente, sobre_pedido

BOLSA = "orders:bolsa"


def agregar(client, producto, cantidad=1, accion="agregar"):
    return client.post(reverse("orders:bolsa_agregar", args=[producto.pk]), {"cantidad": cantidad, "accion": accion})


def continuar(client, direccion=DIRECCION, telefono=TELEFONO):
    return client.post(reverse(BOLSA), {"accion": "continuar", "direccion": direccion, "telefono": telefono})


def mensajes(respuesta):
    return [str(m) for m in respuesta.context["messages"]] if respuesta.context else []


@pytest.fixture
def cliente_con_perfil(cliente):
    cliente.direccion = "Carrera 7 # 12-30, Tunja"
    cliente.telefono = "3001112233"
    cliente.save(update_fields=["direccion", "telefono"])
    return cliente


# --- Agregar a la bolsa desde el detalle ---

@pytest.mark.django_db
def test_comprar_ahora_agrega_y_lleva_a_la_bolsa(client, cliente):
    blusa = disponible(stock=5)
    client.force_login(cliente)
    respuesta = agregar(client, blusa, 2, accion="comprar")
    assert respuesta.status_code == 302 and respuesta.url == reverse(BOLSA)
    assert client.session["bolsa"] == {str(blusa.pk): 2}


@pytest.mark.django_db
def test_agregar_a_la_bolsa_se_queda_en_el_producto_con_mensaje(client, cliente):
    blusa = disponible(stock=5)
    client.force_login(cliente)
    respuesta = agregar(client, blusa, 1)
    assert respuesta.url == reverse("catalog:detalle", args=[blusa.pk])
    pagina = client.get(respuesta.url)
    assert f"Agregaste {blusa.nombre} a tu bolsa." in mensajes(pagina)
    assert client.session["bolsa"] == {str(blusa.pk): 1}
    assert b'data-contador-bolsa>1<' in pagina.content


@pytest.mark.django_db
def test_menos_y_mas_del_detalle_funcionan_sin_javascript(client, cliente):
    blusa = disponible(stock=3)
    client.force_login(cliente)
    detalle = reverse("catalog:detalle", args=[blusa.pk])
    assert agregar(client, blusa, 1, accion="mas").url == f"{detalle}?cantidad=2#comprar"
    assert agregar(client, blusa, 3, accion="mas").url == f"{detalle}?cantidad=3#comprar"
    assert agregar(client, blusa, 1, accion="menos").url == f"{detalle}?cantidad=1#comprar"
    assert agregar(client, blusa, "x", accion="mas").url == f"{detalle}?cantidad=2#comprar"
    assert b'value="2"' in client.get(f"{detalle}?cantidad=2").content
    assert "bolsa" not in client.session


@pytest.mark.django_db
def test_agregar_respeta_topes(client, cliente):
    blusa = disponible(stock=2)
    vestido = sobre_pedido(cantidad_insumo="100")
    client.force_login(cliente)
    respuesta = agregar(client, blusa, 3)
    assert "Solo hay 2 unidades disponibles de Blusa de lino." in mensajes(client.get(respuesta.url))
    respuesta = agregar(client, vestido, 11)
    assert "Puedes solicitar máximo 10 unidades de Vestido midi." in mensajes(client.get(respuesta.url))
    assert client.session.get("bolsa", {}) == {}


@pytest.mark.django_db
def test_agregar_rechaza_producto_inactivo(client, cliente):
    blusa = disponible()
    Producto.objects.filter(pk=blusa.pk).update(activo=False)
    client.force_login(cliente)
    respuesta = agregar(client, blusa)
    assert respuesta.url == reverse("catalog:lista")
    assert client.session.get("bolsa", {}) == {}


@pytest.mark.django_db
def test_visitante_que_agrega_va_al_login_y_vuelve_al_producto(client):
    blusa = disponible()
    for accion in ("comprar", "agregar"):
        respuesta = agregar(client, blusa, accion=accion)
        assert respuesta.status_code == 302
        assert respuesta.url == f"{reverse('accounts:login')}?next=/catalogo/{blusa.pk}/"


# --- Paso 1: bolsa y envío ---

@pytest.mark.django_db
def test_bolsa_vacia_muestra_enlace_al_catalogo(client, cliente):
    client.force_login(cliente)
    respuesta = client.get(reverse(BOLSA))
    assert b"Tu bolsa est\xc3\xa1 vac\xc3\xada" in respuesta.content
    assert reverse("catalog:lista").encode() in respuesta.content
    vacia = client.post(reverse(BOLSA), {"accion": "continuar"}, follow=True)
    assert vacia.redirect_chain == [(reverse(BOLSA), 302)]
    assert "Tu bolsa está vacía." in mensajes(vacia)


@pytest.mark.django_db
def test_bolsa_actualiza_y_quita_y_conserva_el_borrador(client, cliente_con_perfil):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(cantidad_insumo="100")
    client.force_login(cliente_con_perfil)
    agregar(client, blusa, 1)
    agregar(client, vestido, 1)

    inicial = client.get(reverse(BOLSA))
    assert inicial.context["form"]["direccion"].value() == "Carrera 7 # 12-30, Tunja"
    assert inicial.context["fecha_estimada"] is not None

    url = reverse(BOLSA)
    client.post(url, {"accion": f"mas:{blusa.pk}", "direccion": "Calle nueva 1", "telefono": "3205556677"})
    client.post(url, {"accion": f"menos:{vestido.pk}", "direccion": "Calle nueva 1", "telefono": "3205556677"})
    assert client.session["bolsa"] == {str(blusa.pk): 2}
    respuesta = client.get(url)
    assert respuesta.context["form"]["direccion"].value() == "Calle nueva 1"
    assert respuesta.context["form"]["telefono"].value() == "3205556677"
    assert respuesta.context["total"] == Decimal("90000")

    client.post(url, {"accion": f"quitar:{blusa.pk}", "direccion": "Calle nueva 1", "telefono": ""})
    assert client.session["bolsa"] == {}
    assert client.post(url, {"accion": "mas:999999"}).url == url


@pytest.mark.django_db
def test_bolsa_no_supera_el_stock_al_aumentar(client, cliente):
    blusa = disponible(stock=1)
    client.force_login(cliente)
    agregar(client, blusa, 1)
    respuesta = client.post(reverse(BOLSA), {"accion": f"mas:{blusa.pk}"}, follow=True)
    assert "Solo hay 1 unidades disponibles de Blusa de lino." in mensajes(respuesta)
    assert client.session["bolsa"] == {str(blusa.pk): 1}


@pytest.mark.django_db
def test_bolsa_se_conserva_entre_peticiones_de_la_sesion(client, cliente):
    blusa = disponible()
    client.force_login(cliente)
    agregar(client, blusa, 2)
    client.get(reverse("catalog:lista"))
    respuesta = client.get(reverse(BOLSA))
    assert [linea.cantidad for linea in respuesta.context["lineas"]] == [2]


@pytest.mark.django_db
def test_bolsa_sin_direccion_ni_telefono_muestra_error_junto_al_campo(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible())
    respuesta = continuar(client, direccion="", telefono="")
    assert respuesta.status_code == 200
    assert respuesta.context["form"]["direccion"].errors == ["Ingresa la dirección de entrega."]
    assert respuesta.context["form"]["telefono"].errors == ["Ingresa un teléfono de contacto."]
    assert b'id="id_direccion_errors"' in respuesta.content
    respuesta = continuar(client, telefono="12ab")
    assert respuesta.context["form"]["telefono"].errors
    assert not Pedido.objects.exists()


@pytest.mark.django_db
def test_bolsa_muestra_rechazo_por_insumos(client, cliente):
    vestido = sobre_pedido(requerido="2", cantidad_insumo="3")
    client.force_login(cliente)
    agregar(client, vestido, 2)
    respuesta = continuar(client)
    assert respuesta.status_code == 200
    assert "No hay insumos suficientes" in str(respuesta.context["form"].non_field_errors())
    assert RechazoPedido.objects.filter(pedido=None).count() == 1


# --- Flujo completo en 3 pasos ---

@pytest.mark.django_db
def test_flujo_completo_bolsa_pago_exitoso_y_seguimiento(client, cliente):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(dias=4, requerido="1", cantidad_insumo="10")
    client.force_login(cliente)
    agregar(client, blusa, 1, accion="comprar")
    agregar(client, vestido, 2)

    paso1 = continuar(client)
    pedido = Pedido.objects.get()
    assert paso1.url == reverse("orders:pago", args=[pedido.pk])
    pago = client.get(paso1.url)
    assert b"Pago simulado:" in pago.content and b"Entorno sandbox seguro" in pago.content
    assert pedido.numero_visible.encode() in pago.content

    paso2 = client.post(paso1.url, {"resultado": "exitoso", "metodo": "transferencia"})
    assert paso2.url == reverse("orders:seguimiento", args=[pedido.pk])
    seguimiento = client.get(paso2.url)
    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.CONFIRMADO
    assert "¡Pago simulado exitoso! Tu pedido quedó confirmado." in mensajes(seguimiento)
    fecha = pedido.fecha_estimada_entrega
    assert f"{fecha.day} de".encode() in seguimiento.content
    assert seguimiento.context["etapas"][1]["actual"]
    assert "bolsa" not in client.session
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 4
    assert Insumo.objects.get(pk=vestido.receta.get().insumo_id).cantidad_disponible == Decimal("8")


@pytest.mark.django_db
def test_volver_a_continuar_sin_cambios_reutiliza_el_pendiente(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible())
    primero = continuar(client)
    segundo = continuar(client)
    assert primero.url == segundo.url
    assert Pedido.objects.count() == 1


@pytest.mark.django_db
def test_pago_fallido_y_reintento(client, cliente):
    blusa = disponible(stock=5)
    client.force_login(cliente)
    agregar(client, blusa)
    url = continuar(client).url

    fallido = client.post(url, {"resultado": "fallido"}, follow=True)
    assert "Fondos insuficientes (simulado). Puedes reintentar el pago o cancelar el pedido." in mensajes(fallido)
    assert b"Reintentar" in fallido.content and b"Cancelar pedido" in fallido.content
    pedido = Pedido.objects.get()
    assert (pedido.estado, pedido.pago_simulado_estado) == ("Pendiente", "Fallido")
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5

    client.post(url, {"resultado": "exitoso"})
    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.CONFIRMADO
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 4


@pytest.mark.django_db
def test_segundo_envio_del_pago_redirige_con_mensaje_informativo(client, cliente):
    blusa = disponible(stock=5)
    client.force_login(cliente)
    agregar(client, blusa)
    url = continuar(client).url
    client.post(url, {"resultado": "exitoso"})
    segundo = client.post(url, {"resultado": "exitoso"}, follow=True)
    assert segundo.redirect_chain[-1][0] == reverse("orders:seguimiento", args=[Pedido.objects.get().pk])
    assert "Tu pedido ya fue confirmado." in mensajes(segundo)
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 4


@pytest.mark.django_db
def test_pedido_ya_confirmado_por_carrera_redirige_con_mensaje_informativo(client, cliente, monkeypatch):
    client.force_login(cliente)
    agregar(client, disponible())
    url = continuar(client).url

    def ya_confirmado(**kwargs):
        raise PedidoYaConfirmado("Tu pedido ya fue confirmado.")

    monkeypatch.setattr("apps.orders.views.pagar_y_confirmar", ya_confirmado)
    respuesta = client.post(url, {"resultado": "exitoso"}, follow=True)
    assert "Tu pedido ya fue confirmado." in mensajes(respuesta)
    assert not any("error" in m.tags for m in respuesta.context["messages"])


@pytest.mark.django_db
def test_pago_rechazado_por_existencias_vuelve_al_pago_con_error(client, cliente):
    blusa = disponible(stock=2)
    client.force_login(cliente)
    agregar(client, blusa, 2)
    url = continuar(client).url
    Producto.objects.filter(pk=blusa.pk).update(stock_producto=1)
    respuesta = client.post(url, {"resultado": "exitoso"}, follow=True)
    assert respuesta.redirect_chain[-1][0] == url
    assert "No hay unidades suficientes de Blusa de lino." in mensajes(respuesta)
    assert RechazoPedido.objects.filter(pedido__isnull=False).count() == 1


# --- Cancelación y Mis pedidos ---

@pytest.mark.django_db
def test_cliente_cancela_pedido_pendiente(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible())
    continuar(client)
    pedido = Pedido.objects.get()
    url = reverse("orders:cancelar", args=[pedido.pk])
    confirmacion = client.get(url)
    assert b"S\xc3\xad, cancelar pedido" in confirmacion.content
    respuesta = client.post(url, follow=True)
    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.CANCELADO
    assert b"Este pedido fue cancelado" in respuesta.content
    assert "bolsa_pedido_pendiente" not in client.session
    assert client.get(reverse("orders:pago", args=[pedido.pk])).url == reverse(
        "orders:seguimiento", args=[pedido.pk])


@pytest.mark.django_db
def test_cliente_no_cancela_pedido_confirmado(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible())
    url = continuar(client).url
    client.post(url, {"resultado": "exitoso"})
    pedido = Pedido.objects.get()
    cancelar = reverse("orders:cancelar", args=[pedido.pk])
    assert "Solo puedes cancelar pedidos que están en espera de pago." in mensajes(client.get(cancelar, follow=True))
    client.post(cancelar)
    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.CONFIRMADO
    assert "Tu pedido ya fue confirmado." in mensajes(client.get(url, follow=True))


@pytest.mark.django_db
def test_mis_pedidos_lista_solo_los_propios(client, cliente):
    propio = crear_pedido(cliente=cliente, lineas=[{"producto": disponible(), "cantidad": 1}],
                          direccion=DIRECCION, telefono=TELEFONO)
    ajeno = crear_pedido(cliente=otra_cliente(), lineas=[{"producto": disponible(nombre="Otra"), "cantidad": 1}],
                         direccion=DIRECCION, telefono=TELEFONO)
    client.force_login(cliente)
    respuesta = client.get(reverse("orders:mis_pedidos"))
    assert list(respuesta.context["pagina"].object_list) == [propio]
    assert propio.numero_visible.encode() in respuesta.content
    assert ajeno.numero_visible.encode() not in respuesta.content
    assert b"En espera de pago" in respuesta.content


# --- Control de acceso ---

@pytest.mark.django_db
def test_control_de_acceso_por_rol_en_rutas_nuevas(client, cliente, emprendedora):
    pedido = crear_pedido(cliente=cliente, lineas=[{"producto": disponible(), "cantidad": 1}],
                          direccion=DIRECCION, telefono=TELEFONO)
    rutas = [
        reverse(BOLSA), reverse("orders:mis_pedidos"), reverse("orders:pago", args=[pedido.pk]),
        reverse("orders:seguimiento", args=[pedido.pk]), reverse("orders:cancelar", args=[pedido.pk]),
    ]
    for url in rutas:
        respuesta = client.get(url)
        assert respuesta.status_code == 302 and respuesta.url.startswith(reverse("accounts:login"))
    client.force_login(emprendedora)
    for url in rutas:
        assert client.get(url).status_code == 403
    assert agregar(client, disponible(nombre="Otra")).status_code == 403


@pytest.mark.django_db
def test_una_cliente_no_ve_pedidos_de_otra(client, cliente):
    pedido = crear_pedido(cliente=cliente, lineas=[{"producto": disponible(), "cantidad": 1}],
                          direccion=DIRECCION, telefono=TELEFONO)
    client.force_login(otra_cliente())
    for nombre in ("orders:pago", "orders:seguimiento", "orders:cancelar"):
        assert client.get(reverse(nombre, args=[pedido.pk])).status_code == 404
    assert client.post(reverse("orders:pago", args=[pedido.pk]), {"resultado": "exitoso"}).status_code == 404
    assert client.post(reverse("orders:cancelar", args=[pedido.pk])).status_code == 404
    assert Pedido.objects.get(pk=pedido.pk).estado == Pedido.Estado.PENDIENTE


@pytest.mark.django_db
def test_ruta_provisional_redirige_a_la_bolsa(client, cliente):
    client.force_login(cliente)
    assert client.get("/pedidos/en-proceso/").url == reverse(BOLSA)
    assert client.post("/pedidos/en-proceso/").url == reverse(BOLSA)


# --- Rendimiento (RNF-02) ---

def consultas(client, url):
    with CaptureQueriesContext(connection) as contexto:
        assert client.get(url).status_code == 200
    return len(contexto.captured_queries)


@pytest.mark.django_db
def test_consultas_de_bolsa_y_pago_no_crecen_con_las_lineas(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible(nombre="Producto 0"))
    bolsa_una = consultas(client, reverse(BOLSA))
    pago_una = consultas(client, continuar(client).url)

    for indice in range(1, 5):
        agregar(client, sobre_pedido(nombre=f"Producto {indice}", cantidad_insumo="100"))
    bolsa_cinco = consultas(client, reverse(BOLSA))
    pago_cinco = consultas(client, continuar(client).url)

    assert bolsa_cinco == bolsa_una
    assert pago_cinco == pago_una


# --- Plantillas y navegación ---

@pytest.mark.django_db
def test_plantillas_tienen_atributos_de_movil_y_navegacion_de_cliente(client, cliente):
    blusa = disponible()
    client.force_login(cliente)
    detalle = client.get(reverse("catalog:detalle", args=[blusa.pk])).content.decode()
    assert 'inputmode="numeric"' in detalle
    assert 'class="tabbar"' in detalle and 'aria-label="Navegación de la cuenta"' in detalle
    assert ">Salir<" not in detalle
    agregar(client, blusa)
    bolsa = client.get(reverse(BOLSA)).content.decode()
    assert 'autocomplete="street-address"' in bolsa
    assert 'autocomplete="tel"' in bolsa and 'inputmode="tel"' in bolsa
    assert 'class="tabbar"' not in bolsa and 'class="barra-accion"' in bolsa
    assert 'loading="lazy"' in bolsa and 'width="96"' in bolsa
    lista = client.get(reverse("orders:mis_pedidos")).content.decode()
    assert 'aria-current="page">' in lista and "Mis pedidos" in lista


@pytest.mark.django_db
def test_perfil_tiene_boton_cerrar_sesion_y_emprendedora_conserva_salir(client, cliente, emprendedora):
    client.force_login(cliente)
    perfil = client.get(reverse("accounts:perfil")).content.decode()
    assert "Cerrar sesión" in perfil
    assert f'action="{reverse("accounts:logout")}"' in perfil
    client.post(reverse("accounts:logout"))
    assert "_auth_user_id" not in client.session
    client.force_login(emprendedora)
    panel = client.get(reverse("alerts:panel")).content.decode()
    assert ">Salir<" in panel and 'class="tabbar"' not in panel


@pytest.mark.django_db
def test_cerrar_sesion_vacia_la_bolsa(client, cliente):
    client.force_login(cliente)
    agregar(client, disponible())
    client.post(reverse("accounts:logout"))
    client.force_login(cliente)
    assert client.session.get("bolsa") is None
