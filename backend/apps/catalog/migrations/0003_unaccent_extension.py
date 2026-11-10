"""Activa la extensión unaccent requerida por las búsquedas del catálogo."""
from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_alter_producto_precio_alter_producto_stock_minimo_and_more"),
    ]

    operations = [
        UnaccentExtension(),
    ]
