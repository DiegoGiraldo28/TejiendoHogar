"""Triggers del esquema: transiciones de estado e historial inmutable.

Única excepción permitida a la regla de no usar SQL crudo (docs/tejiendohogar_schema1.sql, nota 2).
"""
from django.db import migrations

TRANSICION_SQL = """
CREATE OR REPLACE FUNCTION fn_validar_transicion_pedido()
RETURNS trigger AS $$
BEGIN
    IF NEW.estado = OLD.estado THEN
        RETURN NEW;
    END IF;

    IF (OLD.estado, NEW.estado) IN (
        ('Pendiente',      'Confirmado'),
        ('Pendiente',      'Cancelado'),
        ('Confirmado',     'En_preparacion'),
        ('Confirmado',     'Cancelado'),
        ('En_preparacion', 'Listo'),
        ('Listo',          'Entregado')
    ) THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Transición de estado no permitida: % -> %', OLD.estado, NEW.estado
        USING ERRCODE = 'check_violation';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pedido_transicion_estado
    BEFORE UPDATE OF estado ON pedido
    FOR EACH ROW EXECUTE FUNCTION fn_validar_transicion_pedido();
"""

TRANSICION_REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_pedido_transicion_estado ON pedido;
DROP FUNCTION IF EXISTS fn_validar_transicion_pedido();
"""

HISTORIAL_SQL = """
CREATE OR REPLACE FUNCTION fn_historial_inmutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'historial_estado_pedido es inmutable (RNF-09): no se permite % ', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_historial_inmutable
    BEFORE UPDATE OR DELETE ON historial_estado_pedido
    FOR EACH ROW EXECUTE FUNCTION fn_historial_inmutable();
"""

HISTORIAL_REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_historial_inmutable ON historial_estado_pedido;
DROP FUNCTION IF EXISTS fn_historial_inmutable();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(TRANSICION_SQL, reverse_sql=TRANSICION_REVERSE_SQL),
        migrations.RunSQL(HISTORIAL_SQL, reverse_sql=HISTORIAL_REVERSE_SQL),
    ]
