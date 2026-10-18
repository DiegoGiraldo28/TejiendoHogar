"""Pruebas de insumos, recetas y movimientos."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.management import call_command

from apps.catalog.models import Producto
from apps.inventory.models import Insumo, MovimientoInsumo, ProductoInsumo
from apps.inventory.services import (
    actualizar_insumo, calcular_requerimiento, crear_insumo, eliminar_insumo,
    guardar_receta, insumos_en_stock_bajo, productos_en_stock_bajo,
    registrar_entrada, unidades_fabricables, validar_disponibilidad,
)
from apps.catalog.tests.test_catalog import imagen
from apps.catalog.services import crear_producto


@pytest.fixture(autouse=True)
def media_temporal(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path


def producto(*, tipo=Producto.Tipo.SOBRE_PEDIDO):
    return crear_producto(
        nombre="Prenda", descripcion="Descripción", precio=Decimal("100"),
        imagen=imagen("prenda.png"), tipo=tipo, tiempo_produccion_dias=3,
    )


@pytest.mark.django_db
def test_crear_insumo_con_y_sin_stock_inicial():
    con_stock = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=5)
    sin_stock = crear_insumo(nombre="Hilo", unidad_medida=Insumo.Unidad.CONOS)
    assert con_stock.cantidad_disponible == Decimal("5")
    assert con_stock.movimientoinsumo_set.get().tipo_movimiento == MovimientoInsumo.Tipo.ENTRADA
    assert not sin_stock.movimientoinsumo_set.exists()


@pytest.mark.django_db
def test_insumo_rechaza_nombre_duplicado_sin_distinguir_mayusculas():
    crear_insumo(nombre="Tela Lino", unidad_medida=Insumo.Unidad.METROS)
    with pytest.raises(ValidationError, match="Ya existe"):
        crear_insumo(nombre="tela lino", unidad_medida=Insumo.Unidad.METROS)


@pytest.mark.django_db
def test_entrada_actualiza_existencias_y_crea_movimiento():
    insumo = crear_insumo(nombre="Lana", unidad_medida=Insumo.Unidad.CONOS, cantidad_disponible=2)
    movimiento = registrar_entrada(insumo_id=insumo.pk, cantidad=Decimal("1.25"))
    insumo.refresh_from_db()
    assert insumo.cantidad_disponible == Decimal("3.25")
    assert movimiento.cantidad == Decimal("1.25")
    assert insumo.movimientoinsumo_set.count() == 2


@pytest.mark.django_db
def test_entrada_rechaza_cantidad_no_positiva():
    insumo = crear_insumo(nombre="Algodón", unidad_medida=Insumo.Unidad.METROS)
    with pytest.raises(ValidationError):
        registrar_entrada(insumo_id=insumo.pk, cantidad=0)


@pytest.mark.django_db
def test_entrada_hace_rollback_si_no_se_guarda_el_movimiento():
    insumo = crear_insumo(nombre="Tela", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=2)
    with patch.object(MovimientoInsumo, "save", side_effect=RuntimeError("fallo controlado")):
        with pytest.raises(RuntimeError):
            registrar_entrada(insumo_id=insumo.pk, cantidad=3)
    insumo.refresh_from_db()
    assert insumo.cantidad_disponible == Decimal("2")
    assert insumo.movimientoinsumo_set.count() == 1


@pytest.mark.django_db
def test_editar_insumo_no_cambia_existencias_y_eliminar_en_uso_se_rechaza():
    insumo = crear_insumo(nombre="Botón", unidad_medida=Insumo.Unidad.UNIDADES, cantidad_disponible=8)
    actualizar_insumo(insumo=insumo, nombre="Botón nacar", unidad_medida=Insumo.Unidad.UNIDADES, stock_minimo=2)
    insumo.refresh_from_db()
    assert insumo.cantidad_disponible == Decimal("8")
    with pytest.raises(ValidationError, match="en uso"):
        eliminar_insumo(insumo=insumo)


@pytest.mark.django_db
def test_guardar_receta_y_calcular_requerimiento_exactamente():
    prenda = producto()
    lino = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=10)
    lineas = guardar_receta(producto=prenda, lineas=[{"insumo": lino, "cantidad_requerida": Decimal("1.25")}])
    assert len(lineas) == 1
    assert calcular_requerimiento(producto=prenda, cantidad=3)[lino] == Decimal("3.75")


@pytest.mark.django_db
@pytest.mark.parametrize("cantidad", [0, -1])
def test_receta_rechaza_cantidad_invalida(cantidad):
    prenda = producto()
    lino = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS)
    with pytest.raises(ValidationError):
        guardar_receta(producto=prenda, lineas=[{"insumo": lino, "cantidad_requerida": cantidad}])


@pytest.mark.django_db
def test_receta_rechaza_insumo_repetido():
    prenda = producto()
    lino = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS)
    lineas = [{"insumo": lino, "cantidad_requerida": 1}, {"insumo": lino, "cantidad_requerida": 2}]
    with pytest.raises(ValidationError, match="No repitas"):
        guardar_receta(producto=prenda, lineas=lineas)


@pytest.mark.django_db
def test_validar_disponibilidad_y_unidades_fabricables():
    prenda = producto()
    lino = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=5)
    guardar_receta(producto=prenda, lineas=[{"insumo": lino, "cantidad_requerida": Decimal("1.25")}])
    assert validar_disponibilidad(producto=prenda, cantidad=4)[0]
    disponible, faltantes = validar_disponibilidad(producto=prenda, cantidad=5)
    assert not disponible and faltantes[lino] == Decimal("1.25")
    assert unidades_fabricables(producto=prenda) == 4


@pytest.mark.django_db
def test_stock_bajo_incluye_el_limite_exactamente():
    insumo = crear_insumo(nombre="Tela", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=2, stock_minimo=2)
    disponible = producto(tipo=Producto.Tipo.DISPONIBLE)
    disponible.stock_producto = 1
    disponible.stock_minimo = 1
    disponible.save()
    assert insumo in insumos_en_stock_bajo()
    assert disponible in productos_en_stock_bajo()


@pytest.mark.django_db
@pytest.mark.parametrize("ruta,kwargs", [
    ("inventory:insumos", {}), ("inventory:insumo_nuevo", {}),
    ("inventory:insumo_entrada", {"insumo_id": "insumo"}),
    ("inventory:insumo_eliminar", {"insumo_id": "insumo"}),
    ("inventory:receta", {"producto_id": "producto"}),
])
def test_rutas_de_inventario_protegen_por_rol(client, ruta, kwargs, cliente, emprendedora):
    insumo = crear_insumo(nombre="Tela", unidad_medida=Insumo.Unidad.METROS)
    prenda = producto()
    parametros = {"insumo": insumo.pk, "producto": prenda.pk}
    url = reverse(ruta, kwargs={clave: parametros[valor] for clave, valor in kwargs.items()}) if kwargs else reverse(ruta)
    client.logout()
    assert client.get(url).status_code == 302
    client.force_login(cliente)
    assert client.get(url).status_code == 403
    client.force_login(emprendedora)
    assert client.get(url).status_code in (200, 302)


@pytest.mark.django_db
@pytest.mark.parametrize("ruta,metodo,kwargs", [
    ("alerts:panel", "get", {}),
    ("catalog:productos", "get", {}),
    ("catalog:producto_nuevo", "get", {}),
    ("catalog:producto_editar", "get", {"producto_id": "producto"}),
    ("catalog:producto_estado", "post", {"producto_id": "producto"}),
    ("catalog:producto_eliminar", "get", {"producto_id": "producto"}),
    ("inventory:insumos", "get", {}),
    ("inventory:insumo_nuevo", "get", {}),
    ("inventory:insumo_editar", "get", {"insumo_id": "insumo"}),
    ("inventory:insumo_entrada", "get", {"insumo_id": "insumo"}),
    ("inventory:insumo_movimientos", "get", {"insumo_id": "insumo"}),
    ("inventory:insumo_eliminar", "get", {"insumo_id": "insumo"}),
    ("inventory:receta", "get", {"producto_id": "producto"}),
])
def test_todas_las_rutas_nuevas_aplican_control_de_rol(client, ruta, metodo, kwargs, cliente, emprendedora):
    insumo = crear_insumo(nombre="Material", unidad_medida=Insumo.Unidad.METROS)
    prenda = producto()
    ids = {"insumo": insumo.pk, "producto": prenda.pk}
    url = reverse(ruta, kwargs={clave: ids[valor] for clave, valor in kwargs.items()})
    solicitud = getattr(client, metodo)

    respuesta = solicitud(url)
    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("accounts:login"))

    client.force_login(cliente)
    assert solicitud(url).status_code == 403

    client.force_login(emprendedora)
    assert solicitud(url).status_code in (200, 302)


@pytest.mark.django_db
def test_vistas_crean_insumo_registran_entrada_y_muestran_historial(client, emprendedora):
    client.force_login(emprendedora)
    respuesta = client.post(reverse("inventory:insumo_nuevo"), {
        "nombre": "Tela cruda", "unidad_medida": Insumo.Unidad.METROS,
        "cantidad_disponible": "2.00", "stock_minimo": "1.00",
    })
    insumo = Insumo.objects.get(nombre="Tela cruda")
    assert respuesta.status_code == 302
    assert client.post(reverse("inventory:insumo_entrada", args=[insumo.pk]), {"cantidad": "3.50"}).status_code == 302
    insumo.refresh_from_db()
    assert insumo.cantidad_disponible == Decimal("5.50")
    assert client.get(reverse("inventory:insumo_movimientos", args=[insumo.pk])).status_code == 200


@pytest.mark.django_db
def test_lista_insumos_muestra_formulario_filtra_y_crea_insumo(client, emprendedora):
    client.force_login(emprendedora)
    bajo = crear_insumo(nombre="Tela lino", unidad_medida=Insumo.Unidad.METROS, cantidad_disponible=2, stock_minimo=3)
    crear_insumo(nombre="Hilo blanco", unidad_medida=Insumo.Unidad.CONOS, cantidad_disponible=8, stock_minimo=2)
    respuesta = client.get(reverse("inventory:insumos"), {"q": "Tela", "estado": "bajo"})
    assert respuesta.status_code == 200
    assert b"Registrar material" in respuesta.content
    assert b"Tela lino" in respuesta.content and b"Hilo blanco" not in respuesta.content
    assert reverse("inventory:insumo_entrada", args=[bajo.pk]).encode() in respuesta.content

    creada = client.post(reverse("inventory:insumos"), {
        "nombre": "Cinta nueva", "unidad_medida": Insumo.Unidad.METROS,
        "cantidad_disponible": "4.00", "stock_minimo": "1.00",
    })
    assert creada.status_code == 302
    assert Insumo.objects.filter(nombre="Cinta nueva").exists()


@pytest.mark.django_db
def test_vista_insumo_edita_sin_cantidad_y_elimina_con_post(client, emprendedora):
    client.force_login(emprendedora)
    insumo = crear_insumo(nombre="Hilo", unidad_medida=Insumo.Unidad.CONOS)
    url_editar = reverse("inventory:insumo_editar", args=[insumo.pk])
    assert client.post(url_editar, {
        "nombre": "Hilo blanco", "unidad_medida": Insumo.Unidad.CONOS, "stock_minimo": "2.00",
    }).status_code == 302
    assert client.get(reverse("inventory:insumo_eliminar", args=[insumo.pk])).status_code == 200
    assert client.post(reverse("inventory:insumo_eliminar", args=[insumo.pk])).status_code == 302
    assert not Insumo.objects.filter(pk=insumo.pk).exists()


@pytest.mark.django_db
def test_receta_se_guarda_desde_el_formset(client, emprendedora):
    client.force_login(emprendedora)
    prenda = producto()
    insumo = crear_insumo(nombre="Lino", unidad_medida=Insumo.Unidad.METROS)
    prefijo = "receta"
    datos = {
        f"{prefijo}-TOTAL_FORMS": "1", f"{prefijo}-INITIAL_FORMS": "0",
        f"{prefijo}-MIN_NUM_FORMS": "0", f"{prefijo}-MAX_NUM_FORMS": "1000",
        f"{prefijo}-0-insumo": str(insumo.pk), f"{prefijo}-0-cantidad_requerida": "1.25",
    }
    respuesta = client.post(reverse("inventory:receta", args=[prenda.pk]), datos)
    assert respuesta.status_code == 302
    assert prenda.receta.get().cantidad_requerida == Decimal("1.25")


@pytest.mark.django_db
def test_producto_sobre_pedido_redirige_y_guarda_receta_en_flujo_completo(client, emprendedora):
    client.force_login(emprendedora)
    insumo = crear_insumo(nombre="Lino para vestido", unidad_medida=Insumo.Unidad.METROS)
    respuesta_creacion = client.post(reverse("catalog:producto_nuevo"), {
        "nombre": "Vestido sobre pedido", "descripcion": "Confección artesanal",
        "precio": "45000", "tipo": Producto.Tipo.SOBRE_PEDIDO,
        "tiempo_produccion_dias": "5", "stock_producto": "0", "stock_minimo": "0",
        "imagen": imagen("vestido.png"),
    })
    prenda = Producto.objects.get(nombre="Vestido sobre pedido")
    url_receta = reverse("inventory:receta", args=[prenda.pk])
    assert respuesta_creacion.status_code == 302
    assert respuesta_creacion.url == url_receta
    formulario = client.get(url_receta)
    assert formulario.status_code == 200
    assert b'name="receta-TOTAL_FORMS"' in formulario.content

    respuesta_receta = client.post(url_receta, {
        "receta-TOTAL_FORMS": "1", "receta-INITIAL_FORMS": "0",
        "receta-MIN_NUM_FORMS": "0", "receta-MAX_NUM_FORMS": "1000",
        "receta-0-insumo": str(insumo.pk), "receta-0-cantidad_requerida": "1.25",
    })
    assert respuesta_receta.status_code == 302
    assert prenda.receta.get().cantidad_requerida == Decimal("1.25")


@pytest.mark.django_db
def test_comando_demo_es_idempotente():
    call_command("cargar_datos_demo", verbosity=0)
    primera_cuenta = (Insumo.objects.count(), Producto.objects.count())
    call_command("cargar_datos_demo", verbosity=0)
    assert primera_cuenta == (6, 8)
    assert (Insumo.objects.count(), Producto.objects.count()) == primera_cuenta
    assert Producto.objects.filter(activo=False).exists()
