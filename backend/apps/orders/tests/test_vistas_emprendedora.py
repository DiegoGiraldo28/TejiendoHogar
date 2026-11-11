"""Pruebas funcionales de la Emprendedora: gestión de pedidos, avance de estado y cancelación."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Producto
from apps.common.constants import DIAS_ALISTAMIENTO
from apps.inventory.models import Insumo, MovimientoInsumo
from apps.orders.models import Pedido
from apps.orders.services import (
    cambiar_estado, cancelar_pedido, crear_pedido, pagar_y_confirmar, piezas_entregadas,
)
from .ayudantes import DIRECCION, TELEFONO, disponible, otra_cliente, sobre_pedido

GESTION = "orders:gestion"


def nuevo_pedido(cliente, producto, cantidad=1):
    return crear_pedido(cliente=cliente, lineas=[{"producto": producto, "cantidad": cantidad}],
                        direccion=DIRECCION, telefono=TELEFONO)


def confirmado(cliente, producto, cantidad=1):
    pedido = nuevo_pedido(cliente, producto, cantidad)
    return pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)


def mensajes(respuesta):
    return [str(m) for m in respuesta.context["messages"]]


def panel(client, pedido, **parametros):
    return client.get(reverse("orders:gestion_pedido", args=[pedido.pk]), parametros)


@pytest.mark.django_db
def test_emprendedora_avanza_el_pedido_hasta_entregado_desde_la_interfaz(client, cliente, emprendedora):
    pedido = confirmado(cliente, disponible())
    client.force_login(emprendedora)
    url = reverse("orders:avanzar", args=[pedido.pk])
    for nombre, valor in (("En preparación", "En_preparacion"), ("Listo", "Listo"), ("Entregado", "Entregado")):
        contenido = panel(client, pedido).content.decode()
        assert f'Avanzar a "{nombre}"' in contenido
        respuesta = client.post(url, {"nuevo_estado": valor, "estado": "Confirmado"}, follow=True)
        assert f"El pedido {pedido.numero_visible} pasó a «{nombre}»." in mensajes(respuesta)
        assert respuesta.redirect_chain[-1][0].endswith("?estado=Confirmado")
    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.ENTREGADO
    assert pedido.fecha_entrega_real == timezone.localdate()
    assert pedido.historial.count() == 5
    final = panel(client, pedido).content.decode()
    assert "Avanzar a" not in final and "Cancelar pedido" not in final
    assert "Entregado el" in final


@pytest.mark.django_db
def test_doble_envio_de_avanzar_no_avanza_dos_veces(client, cliente, emprendedora):
    pedido = confirmado(cliente, disponible())
    client.force_login(emprendedora)
    url = reverse("orders:avanzar", args=[pedido.pk])
    client.post(url, {"nuevo_estado": "En_preparacion"})
    segunda = client.post(url, {"nuevo_estado": "En_preparacion"}, follow=True)
    assert "No se puede pasar de «En preparación» a «En preparación»." in mensajes(segunda)
    assert Pedido.objects.get(pk=pedido.pk).estado == Pedido.Estado.EN_PREPARACION
    assert client.get(url).status_code == 405


@pytest.mark.django_db
def test_cancelar_confirmado_devuelve_stock_e_insumos_y_se_ve_en_insumos(client, cliente, emprendedora):
    blusa = disponible(stock=5)
    vestido = sobre_pedido(requerido="2", cantidad_insumo="10")
    insumo = vestido.receta.get().insumo
    pedido = crear_pedido(cliente=cliente, lineas=[
        {"producto": blusa, "cantidad": 2}, {"producto": vestido, "cantidad": 1},
    ], direccion=DIRECCION, telefono=TELEFONO)
    pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 3
    assert Insumo.objects.get(pk=insumo.pk).cantidad_disponible == Decimal("8")

    client.force_login(emprendedora)
    url = reverse("orders:gestion_cancelar", args=[pedido.pk])
    confirmacion = client.get(url, {"estado": "Confirmado"}).content.decode()
    assert "Se devolverán al inventario" in confirmacion and 'name="estado" value="Confirmado"' in confirmacion
    respuesta = client.post(url, {"estado": "Confirmado"}, follow=True)
    assert f"Cancelaste el pedido {pedido.numero_visible}." in mensajes(respuesta)

    pedido.refresh_from_db()
    assert pedido.estado == Pedido.Estado.CANCELADO
    assert Producto.objects.get(pk=blusa.pk).stock_producto == 5
    assert Insumo.objects.get(pk=insumo.pk).cantidad_disponible == Decimal("10")
    assert MovimientoInsumo.objects.filter(pedido=pedido, tipo_movimiento="Devolucion").count() == 1
    contenido = respuesta.content.decode()
    assert "Descuento ·" in contenido and "Devolución ·" in contenido
    insumos = client.get(reverse("inventory:insumo_movimientos", args=[insumo.pk])).content.decode()
    assert "Devolución" in insumos
    assert "10" in client.get(reverse("inventory:insumos")).content.decode()


@pytest.mark.django_db
def test_no_se_cancela_un_pedido_en_preparacion(client, cliente, emprendedora):
    pedido = cambiar_estado(pedido=confirmado(cliente, disponible()), nuevo_estado="En_preparacion",
                            usuario=emprendedora)
    client.force_login(emprendedora)
    url = reverse("orders:gestion_cancelar", args=[pedido.pk])
    assert "Solo se pueden cancelar pedidos Pendientes o Confirmados." in mensajes(client.get(url, follow=True))
    assert "Solo se pueden cancelar pedidos Pendientes o Confirmados." in mensajes(client.post(url, follow=True))
    assert Pedido.objects.get(pk=pedido.pk).estado == Pedido.Estado.EN_PREPARACION
    assert "Cancelar pedido" not in panel(client, pedido).content.decode()


@pytest.fixture
def pedidos_variados(cliente, emprendedora):
    """2 Pendientes, 1 Confirmado, 1 En preparación y 1 Cancelado; uno es de «María José Pérez»."""
    maria = get_user_model().objects.create_user("maria@example.com", "ClaveFuerte-2026", nombre="María José Pérez")
    pendientes = [nuevo_pedido(cliente, disponible(nombre="Gorro")), nuevo_pedido(maria, disponible(nombre="Ruana"))]
    confirmado_ = confirmado(cliente, disponible(nombre="Bufanda"))
    preparacion = cambiar_estado(pedido=confirmado(cliente, disponible(nombre="Mitones")),
                                 nuevo_estado="En_preparacion", usuario=emprendedora)
    cancelado = cancelar_pedido(pedido=nuevo_pedido(cliente, disponible(nombre="Chal")), usuario=cliente)
    return {"pendientes": pendientes, "confirmado": confirmado_, "preparacion": preparacion,
            "cancelado": cancelado, "maria": maria}


@pytest.mark.django_db
def test_filtros_por_estado_con_conteos_correctos(client, emprendedora, pedidos_variados):
    client.force_login(emprendedora)
    respuesta = client.get(reverse(GESTION))
    conteos = {filtro["nombre"]: filtro["conteo"] for filtro in respuesta.context["filtros"]}
    assert conteos == {"Todos": 5, "Pendiente": 2, "Confirmado": 1, "En preparación / confección": 1, "Listo": 0,
                       "Entregado": 0, "Cancelado": 1}
    contenido = respuesta.content.decode()
    assert "Todos (5)" in contenido and "Pendiente (2)" in contenido and 'aria-current="page">Todos (5)' in contenido

    pendientes = client.get(reverse(GESTION), {"estado": "Pendiente"})
    assert {p.pk for p in pendientes.context["pagina"]} == {p.pk for p in pedidos_variados["pendientes"]}
    assert 'aria-current="page">Pendiente (2)' in pendientes.content.decode()
    assert len(client.get(reverse(GESTION), {"estado": "Inventado"}).context["pagina"].object_list) == 5


@pytest.mark.django_db
def test_busqueda_por_numero_y_por_nombre_sin_tildes(client, emprendedora, pedidos_variados):
    client.force_login(emprendedora)
    objetivo = pedidos_variados["confirmado"]
    for texto in (objetivo.numero_visible, f"TH-{objetivo.pk}", str(objetivo.pk)):
        encontrados = list(client.get(reverse(GESTION), {"q": texto}).context["pagina"])
        assert objetivo in encontrados
    por_nombre = client.get(reverse(GESTION), {"q": "maria jose"})
    assert [p.cliente for p in por_nombre.context["pagina"]] == [pedidos_variados["maria"]]
    assert por_nombre.context["filtros"][0]["conteo"] == 1
    vacio = client.get(reverse(GESTION), {"q": "nadie"}).content.decode()
    assert "No hay pedidos que coincidan con el filtro." in vacio


@pytest.mark.django_db
def test_lista_pagina_y_conserva_filtros(client, cliente, emprendedora):
    producto = disponible(stock=50)
    for _ in range(14):
        nuevo_pedido(cliente, producto)
    client.force_login(emprendedora)
    primera = client.get(reverse(GESTION), {"estado": "Pendiente"})
    segunda = client.get(reverse(GESTION), {"estado": "Pendiente", "page": 2})
    assert len(primera.context["pagina"].object_list) == 12
    assert len(segunda.context["pagina"].object_list) == 2
    assert "?estado=Pendiente&page=2" in primera.content.decode()
    pedido = segunda.context["pagina"].object_list[0]
    assert f'/emprendedora/pedidos/{pedido.pk}/?estado=Pendiente&amp;page=2' in segunda.content.decode()


@pytest.mark.django_db
def test_desglose_de_la_fecha_suma_la_fecha_estimada_guardada(client, cliente, emprendedora):
    confirmado(cliente, sobre_pedido(nombre="Previo", dias=3, cantidad_insumo="20"), 2)
    pedido = confirmado(cliente, sobre_pedido(nombre="Actual", dias=4, cantidad_insumo="20"), 1)
    client.force_login(emprendedora)
    respuesta = panel(client, pedido)
    desglose = respuesta.context["desglose"]
    assert desglose["dias_cola"] == 6 and desglose["dias_propios"] == 4
    assert desglose["dias_alistamiento"] == DIAS_ALISTAMIENTO
    total = desglose["dias_cola"] + desglose["dias_propios"] + desglose["dias_alistamiento"]
    assert desglose["fecha_confirmacion"] + timedelta(days=total) == pedido.fecha_estimada_entrega
    contenido = respuesta.content.decode()
    assert "+ Tiempo en cola" in contenido and "6 días" in contenido and "Cálculo de fecha estimada" in contenido


@pytest.mark.django_db
def test_pedido_sin_confirmar_muestra_fecha_pendiente(client, cliente, emprendedora):
    pendiente = nuevo_pedido(cliente, disponible())
    cancelado = cancelar_pedido(pedido=nuevo_pedido(cliente, disponible(nombre="Otra")), usuario=cliente)
    client.force_login(emprendedora)
    for pedido in (pendiente, cancelado):
        respuesta = panel(client, pedido)
        assert respuesta.context["desglose"] is None
        contenido = respuesta.content.decode()
        assert "Fecha pendiente de confirmación" in contenido and "+ Tiempo en cola" not in contenido


@pytest.mark.django_db
def test_nombres_de_estado_de_la_emprendedora_son_los_de_la_base_de_datos(client, cliente, emprendedora):
    pendiente = nuevo_pedido(cliente, disponible())
    client.force_login(emprendedora)
    lista = client.get(reverse(GESTION)).content.decode()
    assert ">Pendiente</span>" in lista and "En espera de pago" not in lista
    assert "En preparación / confección (0)" in lista
    assert [e["nombre"] for e in panel(client, pendiente).context["etapas"]] == [
        "Pendiente", "Confirmado", "En preparación", "Listo", "Entregado",
    ]


def _lineas_del_caso(caso):
    if caso == "confeccion":
        return [{"producto": sobre_pedido(dias=2), "cantidad": 1}]
    if caso == "stock":
        return [{"producto": disponible(), "cantidad": 1}]
    return [{"producto": disponible(), "cantidad": 1}, {"producto": sobre_pedido(dias=2), "cantidad": 1}]


@pytest.mark.django_db
@pytest.mark.parametrize("caso, nombre, descripcion", [
    ("confeccion", "En confección", "Tus piezas se están confeccionando a mano en el taller."),
    ("stock", "En preparación", "La emprendedora está alistando y empacando tu pedido."),
    ("mixto", "En confección", "Tus piezas se están confeccionando a mano en el taller."),
])
def test_en_preparacion_se_nombra_igual_para_cliente_y_emprendedora(
        client, cliente, emprendedora, caso, nombre, descripcion):
    pedido = crear_pedido(cliente=cliente, lineas=_lineas_del_caso(caso), direccion=DIRECCION, telefono=TELEFONO)
    pedido = pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)

    client.force_login(emprendedora)
    confirmado_ = panel(client, pedido).content.decode()
    assert f'Avanzar a "{nombre}"' in confirmado_
    client.post(reverse("orders:avanzar", args=[pedido.pk]), {"nuevo_estado": "En_preparacion"})
    assert Pedido.objects.get(pk=pedido.pk).estado == "En_preparacion"
    respuesta = panel(client, pedido)
    contenido = respuesta.content.decode()
    assert f'<span class="pastilla estado-en_preparacion">{nombre}</span>' in contenido
    assert respuesta.context["etapas"][2]["nombre"] == nombre
    assert "En preparación / confección (1)" in contenido

    client.force_login(cliente)
    seguimiento = client.get(reverse("orders:seguimiento", args=[pedido.pk]))
    assert seguimiento.context["etapas"][2]["nombre"] == nombre
    assert seguimiento.context["etapas"][2]["descripcion"] == descripcion
    assert f">{nombre}</span>" in client.get(reverse("orders:mis_pedidos")).content.decode()


@pytest.mark.django_db
def test_tabla_muestra_productos_resalta_fecha_proxima_y_fila_seleccionada(client, cliente, emprendedora):
    blusa = disponible(nombre="Blusa")
    vestido = sobre_pedido(nombre="Vestido midi", dias=30, cantidad_insumo="20")
    proximo = crear_pedido(cliente=cliente, lineas=[
        {"producto": vestido, "cantidad": 1}, {"producto": blusa, "cantidad": 2},
    ], direccion=DIRECCION, telefono=TELEFONO)
    proximo = pagar_y_confirmar(pedido=proximo, simular_exito=True, usuario=cliente)
    Pedido.objects.filter(pk=proximo.pk).update(fecha_estimada_entrega=timezone.localdate() + timedelta(days=2))
    lejano = confirmado(cliente, vestido)
    client.force_login(emprendedora)
    contenido = panel(client, proximo).content.decode()
    assert "Vestido midi × 1, Blusa × 2" in contenido
    assert contenido.count('class="fecha-alerta"') == 1
    assert 'class="fila-seleccionada"' in contenido and 'aria-current="true"' in contenido
    assert lejano.numero_visible in contenido


@pytest.mark.django_db
def test_lista_y_panel_tienen_consultas_constantes(client, cliente, emprendedora, django_assert_max_num_queries):
    blusa = disponible(stock=50)
    vestido = sobre_pedido(cantidad_insumo="100", requerido="1")

    def crear_con_dos_lineas():
        pedido = crear_pedido(cliente=cliente, lineas=[
            {"producto": blusa, "cantidad": 1}, {"producto": vestido, "cantidad": 1},
        ], direccion=DIRECCION, telefono=TELEFONO)
        return pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)

    primero = crear_con_dos_lineas()
    client.force_login(emprendedora)
    url = reverse("orders:gestion_pedido", args=[primero.pk])
    with CaptureQueriesContext(connection) as con_uno:
        assert client.get(url).status_code == 200
    for _ in range(4):
        crear_con_dos_lineas()
    with django_assert_max_num_queries(len(con_uno.captured_queries)):
        respuesta = client.get(url)
    assert len(respuesta.context["pagina"].object_list) == 5


@pytest.mark.django_db
def test_cliente_recibe_403_y_visitante_va_al_login(client, cliente, emprendedora):
    pedido = confirmado(cliente, disponible())
    rutas = [
        ("get", reverse(GESTION)), ("get", reverse("orders:gestion_pedido", args=[pedido.pk])),
        ("post", reverse("orders:avanzar", args=[pedido.pk])),
        ("get", reverse("orders:gestion_cancelar", args=[pedido.pk])),
        ("post", reverse("orders:gestion_cancelar", args=[pedido.pk])),
    ]
    for metodo, url in rutas:
        respuesta = getattr(client, metodo)(url)
        assert respuesta.status_code == 302 and respuesta.url.startswith(reverse("accounts:login"))
    client.force_login(cliente)
    for metodo, url in rutas:
        assert getattr(client, metodo)(url, {"nuevo_estado": "En_preparacion"}).status_code == 403
    assert Pedido.objects.get(pk=pedido.pk).estado == Pedido.Estado.CONFIRMADO
    client.force_login(otra_cliente())
    assert client.get(reverse(GESTION)).status_code == 403


@pytest.mark.django_db
def test_pedido_inexistente_da_404_y_navegacion_tiene_pedidos(client, emprendedora):
    client.force_login(emprendedora)
    assert client.get(reverse("orders:gestion_pedido", args=[9999])).status_code == 404
    assert client.post(reverse("orders:avanzar", args=[9999])).status_code == 404
    contenido = client.get(reverse(GESTION)).content.decode()
    assert f'<a href="{reverse(GESTION)}" aria-current="page">Pedidos</a>' in contenido
    assert ">Productos</a>" in contenido and ">Insumos</a>" in contenido and ">Panel</a>" in contenido
    assert "Todavía no hay pedidos." in contenido


@pytest.mark.django_db
def test_perfil_emprendedora_suma_piezas_entregadas_en_una_consulta(
        client, cliente, emprendedora, django_assert_num_queries):
    def entregar(pedido):
        for estado in ("En_preparacion", "Listo", "Entregado"):
            pedido = cambiar_estado(pedido=pedido, nuevo_estado=estado, usuario=emprendedora)
        return pedido

    entregar(crear_y_pagar(cliente, [(disponible(nombre="Gorro", stock=10), 2), (disponible(nombre="Chal"), 1)]))
    entregar(confirmado(cliente, sobre_pedido(), 3))
    confirmado(cliente, disponible(nombre="No entregado"), 4)
    nuevo_pedido(cliente, disponible(nombre="Pendiente"), 5)
    with django_assert_num_queries(1):
        assert piezas_entregadas() == 6
    client.force_login(emprendedora)
    contenido = client.get(reverse("accounts:perfil")).content.decode()
    assert "Piezas entregadas</dt>\n          <dd>6</dd>" in contenido


def crear_y_pagar(cliente, productos_y_cantidades):
    pedido = crear_pedido(cliente=cliente, lineas=[
        {"producto": producto, "cantidad": cantidad} for producto, cantidad in productos_y_cantidades
    ], direccion=DIRECCION, telefono=TELEFONO)
    return pagar_y_confirmar(pedido=pedido, simular_exito=True, usuario=cliente)
