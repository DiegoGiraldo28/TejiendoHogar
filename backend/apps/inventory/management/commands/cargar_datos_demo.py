"""Carga un conjunto pequeño e idempotente para recorrer las pantallas."""
import base64

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Producto
from apps.catalog.services import cambiar_estado, crear_producto
from apps.inventory.models import Insumo
from apps.inventory.services import crear_insumo, guardar_receta


# PNG transparente 1x1 generado como bytes; no depende de Pillow.
PNG_DEMO = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jZ3sAAAAASUVORK5CYII="
)

INSUMOS = [
    ("Tela lino crudo", "metros", "1", "10"),
    ("Tela terracota", "metros", "18", "8"),
    ("Hilo blanco No. 40", "conos", "2", "5"),
    ("Cierre metálico 20cm", "unidades", "8", "15"),
    ("Botón nácar 15mm", "unidades", "120", "50"),
    ("Cinta elástica 3cm", "metros", "35", "20"),
]

PRODUCTOS = [
    ("Blusa lino natural", "Disponible", "89000", 1, 1, 4),
    ("Vestido midi terracota", "Sobre_pedido", "156000", 2, 2, 0),
    ("Camisa artesanal a rayas", "Disponible", "102000", 3, 1, 6),
    ("Falda plisada algodón", "Disponible", "98000", 1, 3, 5),
    ("Chaqueta tejida a mano", "Sobre_pedido", "210000", 2, 3, 0),
    ("Pantalón lino recto", "Disponible", "118000", 1, 2, 8),
    ("Top cruzado verano", "Disponible", "65000", 3, 1, 3),
    ("Conjunto dos piezas", "Sobre_pedido", "185000", 2, 2, 0),
]


class Command(BaseCommand):
    help = "Carga datos de muestra para catálogo e inventario; puede ejecutarse varias veces."

    @transaction.atomic
    def handle(self, *args, **options):
        insumos = {}
        for nombre, unidad, cantidad, minimo in INSUMOS:
            insumo = Insumo.objects.filter(nombre__iexact=nombre).first()
            if insumo is None:
                insumo = crear_insumo(
                    nombre=nombre, unidad_medida=unidad,
                    cantidad_disponible=cantidad, stock_minimo=minimo,
                )
            insumos[nombre] = insumo

        for indice, (nombre, tipo, precio, requeridos, dias, stock) in enumerate(PRODUCTOS, start=1):
            producto = Producto.objects.filter(nombre=nombre).first()
            if producto is None:
                producto = crear_producto(
                    nombre=nombre,
                    descripcion=f"Prenda artesanal TejiendoHogar: {nombre.lower()}.",
                    precio=precio,
                    imagen=ContentFile(PNG_DEMO, name=f"demo-{indice}.png"),
                    tipo=tipo,
                    tiempo_produccion_dias=dias,
                    stock_producto=stock,
                    stock_minimo=2,
                )
            if tipo == Producto.Tipo.SOBRE_PEDIDO and not producto.receta.exists():
                nombre_insumo = "Tela lino crudo" if indice == 2 else "Tela terracota"
                guardar_receta(producto=producto, lineas=[
                    {"insumo": insumos[nombre_insumo], "cantidad_requerida": "1.25"},
                    {"insumo": insumos["Botón nácar 15mm"], "cantidad_requerida": "3"},
                ])
                if nombre != "Conjunto dos piezas":
                    cambiar_estado(producto=producto)
            if nombre == "Top cruzado verano" and producto.activo:
                cambiar_estado(producto=producto)

        self.stdout.write(self.style.SUCCESS("Datos de demostración cargados correctamente."))
