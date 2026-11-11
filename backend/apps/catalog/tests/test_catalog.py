"""Pruebas de productos, servicios y acceso a la gestión."""
from decimal import Decimal

import pytest
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from apps.catalog.models import Producto
from apps.catalog.services import (
    actualizar_producto, cambiar_estado, crear_producto, eliminar_producto, listar_publicos,
    obtener_publico,
)
from apps.inventory.models import Insumo, ProductoInsumo

from conftest import (crear_producto_prueba as crear, imagen_cabecera_prueba,
                      imagen_png_prueba as imagen)

PNG = imagen().read()


@pytest.mark.django_db
def test_crear_disponible_activo_y_sobre_pedido_inactivo():
    disponible = crear()
    encargo = crear(tipo=Producto.Tipo.SOBRE_PEDIDO, nombre="Vestido")
    assert disponible.activo and disponible.stock_producto == 4
    assert not encargo.activo and encargo.stock_producto == 0


@pytest.mark.django_db
@pytest.mark.parametrize("campo,valor", [
    ("precio", -1), ("tiempo_produccion_dias", 0), ("stock_producto", -1), ("stock_minimo", -1),
])
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
@pytest.mark.parametrize(("formato", "variante"), [
    ("png", ""), ("jpg", "sof0"), ("jpg", "sof2"),
    ("webp", "vp8"), ("webp", "vp8l"), ("webp", "vp8x"),
])
def test_imagen_de_200_por_200_se_acepta_en_todos_los_formatos(formato, variante):
    producto = crear(imagen=imagen_cabecera_prueba(formato, variante=variante))
    assert producto.pk


@pytest.mark.django_db
@pytest.mark.parametrize("formato", ["png", "jpg", "webp"])
def test_imagen_menor_a_200_por_200_se_rechaza(formato):
    with pytest.raises(ValidationError, match="200 × 200"):
        crear(imagen=imagen_cabecera_prueba(formato, ancho=199, alto=200))


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
def test_listado_publico_filtra_activos_busqueda_y_tipo():
    crear(nombre="Blusa uno")
    crear(nombre="Blusa dos")
    inactivo = crear(nombre="Inactivo")
    inactivo.activo = False
    inactivo.save()
    productos = listar_publicos(busqueda="blusa", tipo=Producto.Tipo.DISPONIBLE)
    assert productos.count() == 2
    assert all(p.activo for p in productos)


@pytest.mark.django_db
def test_obtener_publico_oculta_inactivo():
    producto = crear()
    assert obtener_publico(id_producto=producto.pk).pk == producto.pk
    producto.activo = False
    producto.save()
    assert obtener_publico(id_producto=producto.pk) is None


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", [
    "catalog:productos", "catalog:producto_nuevo", "inventory:insumos", "inventory:insumo_nuevo",
    "alerts:panel",
])
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


@pytest.mark.django_db
def test_formulario_producto_muestra_error_espanol_para_cero_dias(client, emprendedora):
    client.force_login(emprendedora)
    respuesta = client.post(reverse("catalog:producto_nuevo"), {
        "nombre": "Blusa", "descripcion": "Tejida", "precio": "100",
        "tipo": Producto.Tipo.SOBRE_PEDIDO, "tiempo_produccion_dias": "0",
        "stock_producto": "0", "stock_minimo": "0", "imagen": imagen(),
    })
    assert respuesta.status_code == 200
    assert "Los d\u00edas de producci\u00f3n deben ser al menos 1".encode() in respuesta.content


@pytest.mark.django_db
def test_producto_disponible_guarda_un_dia_de_confeccion_aunque_no_se_envie(client, emprendedora):
    client.force_login(emprendedora)
    base = {
        "descripcion": "Tejida", "precio": "100", "tipo": Producto.Tipo.DISPONIBLE,
        "stock_producto": "2", "stock_minimo": "0",
    }
    client.post(reverse("catalog:producto_nuevo"), {**base, "nombre": "Sin campo", "imagen": imagen()})
    client.post(reverse("catalog:producto_nuevo"), {
        **base, "nombre": "Con campo", "tiempo_produccion_dias": "9", "imagen": imagen(),
    })
    assert Producto.objects.get(nombre="Sin campo").tiempo_produccion_dias == 1
    assert Producto.objects.get(nombre="Con campo").tiempo_produccion_dias == 1


@pytest.mark.django_db
def test_producto_sobre_pedido_exige_dias_de_confeccion(client, emprendedora):
    client.force_login(emprendedora)
    respuesta = client.post(reverse("catalog:producto_nuevo"), {
        "nombre": "Ruana", "descripcion": "Tejida", "precio": "100",
        "tipo": Producto.Tipo.SOBRE_PEDIDO, "imagen": imagen(),
    })
    assert respuesta.status_code == 200
    assert "obligatorio para un producto Sobre pedido".encode() in respuesta.content
    assert not Producto.objects.filter(nombre="Ruana").exists()


@pytest.mark.django_db
def test_editar_a_disponible_guarda_un_dia_y_el_formulario_marca_el_campo(client, emprendedora):
    producto = crear_producto(
        nombre="Gorro", descripcion="Lana", precio="100", imagen=imagen(), tipo=Producto.Tipo.SOBRE_PEDIDO,
        tiempo_produccion_dias=6,
    )
    actualizar_producto(
        producto=producto, nombre="Gorro", descripcion="Lana", precio="100", tipo=Producto.Tipo.DISPONIBLE,
        tiempo_produccion_dias=6, stock_producto=1,
    )
    producto.refresh_from_db()
    assert producto.tiempo_produccion_dias == 1
    client.force_login(emprendedora)
    formulario = client.get(reverse("catalog:producto_editar", args=[producto.pk])).content
    assert b"data-sobre-pedido-fields" in formulario
