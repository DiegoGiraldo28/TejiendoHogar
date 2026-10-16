"""Pruebas de productos, servicios y acceso a la gestión."""
from decimal import Decimal

import pytest
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from apps.catalog.models import Producto
from apps.catalog.services import (
    actualizar_producto, cambiar_estado, crear_producto, eliminar_producto, listar_publicos,
    obtener_publico,
)
from apps.inventory.models import Insumo, ProductoInsumo

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def imagen(nombre="prenda.png", contenido=PNG):
    return SimpleUploadedFile(nombre, contenido, content_type="image/png")


def crear(*, tipo=Producto.Tipo.DISPONIBLE, **cambios):
    datos = {
        "nombre": "Blusa artesanal", "descripcion": "Hecha a mano",
        "precio": Decimal("45000"), "imagen": imagen(), "tipo": tipo,
        "tiempo_produccion_dias": 5, "stock_producto": 4, "stock_minimo": 1,
    }
    datos.update(cambios)
    return crear_producto(**datos)


@pytest.mark.django_db
def test_crear_disponible_activo_y_sobre_pedido_inactivo():
    disponible = crear()
    encargo = crear(tipo=Producto.Tipo.SOBRE_PEDIDO, nombre="Vestido")
    assert disponible.activo and disponible.stock_producto == 4
    assert not encargo.activo and encargo.stock_producto == 0


@pytest.mark.django_db
@pytest.mark.parametrize("campo,valor", [("precio", -1), ("tiempo_produccion_dias", 0), ("stock_producto", -1), ("stock_minimo", -1)])
def test_check_producto_rechaza_valores_invalidos(campo, valor):
    producto = crear()
    setattr(producto, campo, valor)
    with pytest.raises(ValidationError):
        producto.full_clean()


@pytest.mark.django_db
def test_producto_rechaza_descripcion_vacia():
    with pytest.raises(ValidationError):
        crear(descripcion="   ")


@pytest.mark.django_db
@pytest.mark.parametrize("nombre,contenido", [("prenda.gif", PNG), ("prenda.png", b"no es png")])
def test_producto_rechaza_extension_o_firma_invalida(nombre, contenido):
    with pytest.raises(ValidationError):
        crear(imagen=imagen(nombre, contenido))


@pytest.mark.django_db
def test_producto_rechaza_imagen_mayor_a_dos_mb():
    with pytest.raises(ValidationError):
        crear(imagen=imagen(contenido=PNG + b"x" * (2 * 1024 * 1024)))


@pytest.mark.django_db
def test_sobre_pedido_requiere_receta_para_activarse():
    producto = crear(tipo=Producto.Tipo.SOBRE_PEDIDO)
    with pytest.raises(ValidationError, match="receta"):
        cambiar_estado(producto=producto)
    insumo = Insumo.objects.create(nombre="Lino", unidad_medida=Insumo.Unidad.METROS)
    ProductoInsumo.objects.create(producto=producto, insumo=insumo, cantidad_requerida=1)
    assert cambiar_estado(producto=producto).activo


@pytest.mark.django_db
def test_eliminar_producto_sin_relaciones():
    producto = crear()
    eliminar_producto(producto=producto)
    assert not Producto.objects.filter(pk=producto.pk).exists()


@pytest.mark.django_db
def test_eliminar_producto_informa_relacion_protegida():
    producto = crear()
    with patch.object(Producto, "delete", side_effect=ProtectedError("en uso", set())):
        with pytest.raises(ValidationError, match="pedidos asociados"):
            eliminar_producto(producto=producto)


@pytest.mark.django_db
def test_actualizar_producto_conserva_imagen_si_no_se_reemplaza():
    producto = crear()
    imagen_original = producto.imagen.name
    actualizado = actualizar_producto(
        producto=producto, nombre="Blusa modificada", descripcion="Nueva descripción",
        precio=Decimal("50000"), tipo=Producto.Tipo.DISPONIBLE,
        tiempo_produccion_dias=6, stock_producto=3, stock_minimo=1,
    )
    assert actualizado.imagen.name == imagen_original
    assert actualizado.nombre == "Blusa modificada"


@pytest.mark.django_db
def test_listado_publico_filtra_activos_busqueda_tipo_y_pagina():
    crear(nombre="Blusa uno")
    crear(nombre="Blusa dos")
    inactivo = crear(nombre="Inactivo")
    inactivo.activo = False
    inactivo.save()
    pagina = listar_publicos(busqueda="blusa", tipo=Producto.Tipo.DISPONIBLE).get_page(1)
    assert pagina.paginator.count == 2
    assert all(p.activo for p in pagina.object_list)


@pytest.mark.django_db
def test_obtener_publico_oculta_inactivo():
    producto = crear()
    assert obtener_publico(id_producto=producto.pk).pk == producto.pk
    producto.activo = False
    producto.save()
    with pytest.raises(Http404):
        obtener_publico(id_producto=producto.pk)


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", ["catalog:productos", "catalog:producto_nuevo", "inventory:insumos", "inventory:insumo_nuevo", "alerts:panel"])
def test_rutas_gestion_protegen_por_rol(client, ruta, cliente, emprendedora):
    url = reverse(ruta)
    client.logout()
    assert client.get(url).status_code == 302
    client.force_login(cliente)
    assert client.get(url).status_code == 403
    client.force_login(emprendedora)
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_flujo_producto_disponible_editar_estado_y_eliminar_por_post(client, emprendedora):
    client.force_login(emprendedora)
    datos = {
        "nombre": "Blusa de prueba", "descripcion": "Prenda tejida",
        "precio": "45000", "tipo": Producto.Tipo.DISPONIBLE,
        "tiempo_produccion_dias": "5", "stock_producto": "3", "stock_minimo": "1",
    }
    respuesta = client.post(reverse("catalog:producto_nuevo"), {**datos, "imagen": imagen()})
    producto = Producto.objects.get(nombre="Blusa de prueba")
    assert respuesta.status_code == 302 and producto.activo
    assert client.get(reverse("catalog:producto_eliminar", args=[producto.pk])).status_code == 200
    assert client.post(reverse("catalog:producto_estado", args=[producto.pk])).status_code == 302
    producto.refresh_from_db()
    assert not producto.activo
    client.post(reverse("catalog:producto_eliminar", args=[producto.pk]))
    assert not Producto.objects.filter(pk=producto.pk).exists()


@pytest.mark.django_db
def test_formulario_producto_rechaza_imagen_invalida(client, emprendedora):
    client.force_login(emprendedora)
    datos = {
        "nombre": "Blusa", "descripcion": "Tejida", "precio": "100",
        "tipo": Producto.Tipo.DISPONIBLE, "tiempo_produccion_dias": "2",
        "stock_producto": "0", "stock_minimo": "0",
        "imagen": imagen("mala.png", b"no es png"),
    }
    respuesta = client.post(reverse("catalog:producto_nuevo"), datos)
    assert respuesta.status_code == 200
    assert "contenido del archivo" in respuesta.content.decode()
