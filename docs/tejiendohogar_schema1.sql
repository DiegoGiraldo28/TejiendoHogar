-- ============================================================
-- TejiendoHogar - Esquema de Base de Datos (PostgreSQL)
-- Proyecto: TejiendoHogar - Ingeniería de Software III
-- Motor: PostgreSQL 14+ (probado en PostgreSQL 16)
-- Versión: 2 - ajustada a la Definición del Proyecto, el PGCP (RNF) y el C4 (ADR)
-- Convención de nombres: snake_case, compatible con Django ORM
-- La base de datos debe crearse con codificación UTF8
--
-- Ejecución:
--   psql -v ON_ERROR_STOP=1 -d tejiendohogar -f tejiendohogar_schema.sql
-- ============================================================
--
-- CAMBIOS RESPECTO A LA VERSIÓN 1
--  1. Nueva tabla historial_estado_pedido: log de auditoría inmutable de los
--     cambios de estado (RNF-09).
--  2. producto: se elimina ventas_ultimos_30_dias (las alertas se calculan al
--     momento, ADR-04); descripcion e imagen_url pasan a NOT NULL (RNF-28);
--     se agrega stock_minimo (la Definición habla de "producto o insumo");
--     se elimina id_emprendedora (el sistema atiende a un solo taller).
--  3. detalle_pedido: se agregan origen y dias_produccion, que se fijan al
--     confirmar el pedido. Permiten cancelar y calcular la cola sin depender
--     de datos que luego puedan cambiar.
--  4. pedido: estado Cancelado con checks de coherencia, fechas como DATE donde
--     se mide en días, y trigger que exige las transiciones válidas.
--  5. movimiento_insumo: cada tipo de movimiento exige o prohíbe id_pedido.
--  6. Nueva tabla rechazo_pedido: respalda la métrica "pedidos rechazados por
--     falta de insumos".
--  7. TIMESTAMPTZ en lugar de TIMESTAMP (Django con USE_TZ=True) y claves
--     foráneas RESTRICT: los pedidos no se eliminan, se cancelan.
--  8. usuario: se agregan telefono y direccion (perfil del cliente). pedido
--     guarda una copia (direccion_entrega y telefono_contacto) al crearse, para
--     que cambiar el perfil después no altere pedidos ya hechos.
-- ============================================================

BEGIN;

-- ============================================================
-- TABLA: usuario
-- Roles permitidos: Emprendedora, Cliente, Operaria (reservado,
-- sin vista propia según Definición del Proyecto §3.1)
-- ============================================================
CREATE TABLE usuario (
    id_usuario          SERIAL PRIMARY KEY,
    nombre              VARCHAR(150) NOT NULL,
    correo              VARCHAR(150) NOT NULL,
    contrasena_hash     VARCHAR(255) NOT NULL,
    telefono            VARCHAR(20),
    direccion           VARCHAR(255),
    rol                 VARCHAR(20)  NOT NULL,
    activo              BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_registro      TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_usuario_correo UNIQUE (correo),
    CONSTRAINT ck_usuario_rol CHECK (rol IN ('Emprendedora', 'Cliente', 'Operaria')),
    CONSTRAINT ck_usuario_telefono CHECK (telefono IS NULL OR telefono ~ '^[0-9+ ()-]{7,20}$'),
    CONSTRAINT ck_usuario_direccion CHECK (direccion IS NULL OR btrim(direccion) <> '')
);

CREATE INDEX idx_usuario_rol ON usuario (rol);
CREATE INDEX idx_usuario_activo ON usuario (activo);

COMMENT ON TABLE usuario IS 'Gestión de Usuarios y Autenticación (Definición §4.1)';
COMMENT ON COLUMN usuario.telefono IS 'Datos básicos del perfil (Cliente). Opcional al registrarse; se exige al crear un pedido.';
COMMENT ON COLUMN usuario.direccion IS 'Dirección de entrega predeterminada del cliente. Opcional al registrarse; se exige al crear un pedido.';
COMMENT ON COLUMN usuario.rol IS 'Emprendedora y Cliente operativos; Operaria reservado sin vista propia';

-- ============================================================
-- TABLA: producto
-- Catálogo de productos (Definición §4.2)
-- ============================================================
CREATE TABLE producto (
    id_producto             SERIAL PRIMARY KEY,
    nombre                  VARCHAR(150)  NOT NULL,
    descripcion             TEXT          NOT NULL,
    precio                  NUMERIC(10,2) NOT NULL,
    imagen_url              VARCHAR(255)  NOT NULL,
    tipo                    VARCHAR(20)   NOT NULL,
    tiempo_produccion_dias  INT           NOT NULL,
    stock_producto          INT           NOT NULL DEFAULT 0,
    stock_minimo            INT           NOT NULL DEFAULT 0,
    activo                  BOOLEAN       NOT NULL DEFAULT TRUE,
    fecha_creacion          TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_actualizacion     TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_producto_tipo CHECK (tipo IN ('Disponible', 'Sobre_pedido')),
    CONSTRAINT ck_producto_precio CHECK (precio >= 0),
    CONSTRAINT ck_producto_tiempo_produccion CHECK (tiempo_produccion_dias > 0),
    CONSTRAINT ck_producto_stock CHECK (stock_producto >= 0),
    CONSTRAINT ck_producto_stock_minimo CHECK (stock_minimo >= 0),
    CONSTRAINT ck_producto_descripcion CHECK (btrim(descripcion) <> ''),
    CONSTRAINT ck_producto_imagen CHECK (btrim(imagen_url) <> '')
);

CREATE INDEX idx_producto_activo ON producto (activo);
CREATE INDEX idx_producto_tipo ON producto (tipo);

COMMENT ON TABLE producto IS 'Gestión de Catálogo de Productos (Definición §4.2). Todos los campos son obligatorios (RNF-28).';
COMMENT ON COLUMN producto.tiempo_produccion_dias IS 'Obligatorio: insumo del Motor de Cálculo de Fecha Estimada (RNF-27). En productos Disponible no suma a la cola mientras haya stock.';
COMMENT ON COLUMN producto.stock_producto IS 'Solo relevante cuando tipo = Disponible';
COMMENT ON COLUMN producto.stock_minimo IS 'Umbral de la Regla 1 del Asistente PLUS para productos Disponible';

-- ============================================================
-- TABLA: insumo
-- Control de Materia Prima e Insumos (Definición §4.4)
-- ============================================================
CREATE TABLE insumo (
    id_insumo            SERIAL PRIMARY KEY,
    nombre               VARCHAR(150)  NOT NULL,
    unidad_medida        VARCHAR(20)   NOT NULL,
    cantidad_disponible  NUMERIC(10,2) NOT NULL DEFAULT 0,
    stock_minimo         NUMERIC(10,2) NOT NULL DEFAULT 0,
    fecha_actualizacion  TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_insumo_nombre UNIQUE (nombre),
    CONSTRAINT ck_insumo_cantidad CHECK (cantidad_disponible >= 0),
    CONSTRAINT ck_insumo_stock_minimo CHECK (stock_minimo >= 0)
);

CREATE INDEX idx_insumo_cantidad_disponible ON insumo (cantidad_disponible);

COMMENT ON TABLE insumo IS 'Control de Materia Prima e Insumos (Definición §4.4). El CHECK de cantidad impide stock negativo aunque falle la validación de la aplicación.';

-- ============================================================
-- TABLA: producto_insumo (Lista de materiales / BOM)
-- Relación N:N entre producto e insumo (Definición §3.2)
-- ============================================================
CREATE TABLE producto_insumo (
    id_producto_insumo  SERIAL PRIMARY KEY,
    id_producto         INT           NOT NULL,
    id_insumo           INT           NOT NULL,
    cantidad_requerida  NUMERIC(10,2) NOT NULL,

    CONSTRAINT fk_prodinsumo_producto FOREIGN KEY (id_producto)
        REFERENCES producto (id_producto) ON DELETE CASCADE,
    CONSTRAINT fk_prodinsumo_insumo FOREIGN KEY (id_insumo)
        REFERENCES insumo (id_insumo) ON DELETE RESTRICT,
    CONSTRAINT uq_producto_insumo UNIQUE (id_producto, id_insumo),
    CONSTRAINT ck_prodinsumo_cantidad CHECK (cantidad_requerida > 0)
);

CREATE INDEX idx_prodinsumo_producto ON producto_insumo (id_producto);
CREATE INDEX idx_prodinsumo_insumo ON producto_insumo (id_insumo);

COMMENT ON TABLE producto_insumo IS 'BOM: cantidad de cada insumo necesaria por unidad de producto';

-- ============================================================
-- TABLA: pedido
-- Gestión de Pedidos (Definición §4.3)
-- Flujo: Pendiente -> Confirmado -> En_preparacion -> Listo -> Entregado
-- Cancelado solo se alcanza desde Pendiente o Confirmado
-- ============================================================
CREATE TABLE pedido (
    id_pedido               SERIAL PRIMARY KEY,
    id_cliente              INT           NOT NULL,
    estado                  VARCHAR(20)   NOT NULL DEFAULT 'Pendiente',
    subtotal                NUMERIC(10,2) NOT NULL,
    direccion_entrega       VARCHAR(255)  NOT NULL,
    telefono_contacto       VARCHAR(20)   NOT NULL,
    pago_simulado_estado    VARCHAR(20),
    fecha_creacion          TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_confirmacion      TIMESTAMPTZ,
    fecha_estimada_entrega  DATE,
    fecha_entrega_real      DATE,
    fecha_cancelacion       TIMESTAMPTZ,

    CONSTRAINT fk_pedido_cliente FOREIGN KEY (id_cliente)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_pedido_estado CHECK (
        estado IN ('Pendiente', 'Confirmado', 'En_preparacion', 'Listo', 'Entregado', 'Cancelado')
    ),
    CONSTRAINT ck_pedido_pago_estado CHECK (
        pago_simulado_estado IS NULL OR pago_simulado_estado IN ('Exitoso', 'Fallido')
    ),
    CONSTRAINT ck_pedido_subtotal CHECK (subtotal >= 0),
    CONSTRAINT ck_pedido_direccion CHECK (btrim(direccion_entrega) <> ''),
    CONSTRAINT ck_pedido_telefono CHECK (telefono_contacto ~ '^[0-9+ ()-]{7,20}$'),
    -- RNF-30: solo un pago exitoso lleva a Confirmado
    CONSTRAINT ck_pedido_pago_exitoso CHECK (
        estado NOT IN ('Confirmado', 'En_preparacion', 'Listo', 'Entregado')
        OR COALESCE(pago_simulado_estado, '') = 'Exitoso'
    ),
    -- Un pedido aceptado ya tiene fecha de confirmación y fecha estimada (Motor de Fecha)
    CONSTRAINT ck_pedido_confirmado_datos CHECK (
        estado NOT IN ('Confirmado', 'En_preparacion', 'Listo', 'Entregado')
        OR (fecha_confirmacion IS NOT NULL AND fecha_estimada_entrega IS NOT NULL)
    ),
    CONSTRAINT ck_pedido_cancelacion CHECK ((estado = 'Cancelado') = (fecha_cancelacion IS NOT NULL)),
    CONSTRAINT ck_pedido_entrega CHECK ((estado = 'Entregado') = (fecha_entrega_real IS NOT NULL))
);

CREATE INDEX idx_pedido_cliente ON pedido (id_cliente);
CREATE INDEX idx_pedido_estado ON pedido (estado);
CREATE INDEX idx_pedido_fecha_estimada ON pedido (fecha_estimada_entrega);
CREATE INDEX idx_pedido_estado_confirmacion ON pedido (estado, fecha_confirmacion);

COMMENT ON TABLE pedido IS 'Gestión de Pedidos (Definición §4.3). Los pedidos no se eliminan: se cancelan.';
COMMENT ON COLUMN pedido.direccion_entrega IS 'Copia de la dirección al crear el pedido (del perfil o digitada en el checkout). No cambia si el cliente edita su perfil.';
COMMENT ON COLUMN pedido.telefono_contacto IS 'Copia del teléfono al crear el pedido, igual que direccion_entrega.';
COMMENT ON COLUMN pedido.estado IS 'Pendiente->Confirmado->En_preparacion->Listo->Entregado; Cancelado solo desde Pendiente o Confirmado';
COMMENT ON COLUMN pedido.fecha_entrega_real IS 'Se compara con fecha_estimada_entrega para medir la precisión del Motor de Fecha';

-- Transiciones de estado válidas (incluye la regla de cancelación)
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

-- ============================================================
-- TABLA: detalle_pedido
-- Relación N:N entre pedido y producto con atributos propios
-- precio_unitario: congela el precio histórico al momento del pedido
-- origen y dias_produccion: se fijan al confirmar el pedido
-- ============================================================
CREATE TABLE detalle_pedido (
    id_detalle       SERIAL PRIMARY KEY,
    id_pedido        INT           NOT NULL,
    id_producto      INT           NOT NULL,
    cantidad         INT           NOT NULL,
    precio_unitario  NUMERIC(10,2) NOT NULL,
    origen           VARCHAR(10),
    dias_produccion  INT,

    CONSTRAINT fk_detalle_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedido (id_pedido) ON DELETE RESTRICT,
    CONSTRAINT fk_detalle_producto FOREIGN KEY (id_producto)
        REFERENCES producto (id_producto) ON DELETE RESTRICT,
    CONSTRAINT uq_detalle_pedido_producto UNIQUE (id_pedido, id_producto),
    CONSTRAINT ck_detalle_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_detalle_precio CHECK (precio_unitario >= 0),
    CONSTRAINT ck_detalle_origen CHECK (origen IS NULL OR origen IN ('Stock', 'Confeccion')),
    CONSTRAINT ck_detalle_dias CHECK (dias_produccion IS NULL OR dias_produccion >= 0),
    CONSTRAINT ck_detalle_origen_dias CHECK ((origen IS NULL) = (dias_produccion IS NULL))
);

CREATE INDEX idx_detalle_pedido ON detalle_pedido (id_pedido);
CREATE INDEX idx_detalle_producto ON detalle_pedido (id_producto);

COMMENT ON TABLE detalle_pedido IS 'Líneas del pedido. precio_unitario preserva el valor histórico.';
COMMENT ON COLUMN detalle_pedido.origen IS 'Se fija al confirmar. Stock: se restó stock_producto (producto Disponible). Confeccion: se descontaron insumos (producto Sobre_pedido). Define qué se restaura al cancelar.';
COMMENT ON COLUMN detalle_pedido.dias_produccion IS 'Copia de producto.tiempo_produccion_dias al confirmar (0 si origen = Stock). La cola del Motor de Fecha suma cantidad * dias_produccion.';

-- ============================================================
-- TABLA: movimiento_insumo
-- Trazabilidad de entradas, descuentos y devoluciones de insumos
-- ============================================================
CREATE TABLE movimiento_insumo (
    id_movimiento     SERIAL PRIMARY KEY,
    id_insumo         INT           NOT NULL,
    id_pedido         INT,
    tipo_movimiento   VARCHAR(20)   NOT NULL,
    cantidad          NUMERIC(10,2) NOT NULL,
    fecha_movimiento  TIMESTAMPTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_movimiento_insumo FOREIGN KEY (id_insumo)
        REFERENCES insumo (id_insumo) ON DELETE RESTRICT,
    CONSTRAINT fk_movimiento_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedido (id_pedido) ON DELETE RESTRICT,
    CONSTRAINT ck_movimiento_tipo CHECK (
        tipo_movimiento IN ('Entrada', 'Descuento', 'Devolucion')
    ),
    CONSTRAINT ck_movimiento_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_movimiento_pedido CHECK (
        (tipo_movimiento = 'Entrada' AND id_pedido IS NULL)
        OR (tipo_movimiento IN ('Descuento', 'Devolucion') AND id_pedido IS NOT NULL)
    )
);

CREATE INDEX idx_movimiento_insumo ON movimiento_insumo (id_insumo);
CREATE INDEX idx_movimiento_pedido ON movimiento_insumo (id_pedido);
CREATE INDEX idx_movimiento_tipo ON movimiento_insumo (tipo_movimiento);

COMMENT ON TABLE movimiento_insumo IS 'Entrada: registro manual de insumo. Descuento: al confirmar pedido. Devolucion: al cancelar un pedido Confirmado, con las mismas cantidades de sus movimientos Descuento.';

-- ============================================================
-- TABLA: historial_estado_pedido
-- Log de auditoría inmutable de cambios de estado (RNF-09)
-- ============================================================
CREATE TABLE historial_estado_pedido (
    id_historial     SERIAL PRIMARY KEY,
    id_pedido        INT         NOT NULL,
    id_usuario       INT         NOT NULL,
    estado_anterior  VARCHAR(20),
    estado_nuevo     VARCHAR(20) NOT NULL,
    fecha_cambio     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_historial_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedido (id_pedido) ON DELETE RESTRICT,
    CONSTRAINT fk_historial_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_historial_estado_anterior CHECK (
        estado_anterior IS NULL
        OR estado_anterior IN ('Pendiente', 'Confirmado', 'En_preparacion', 'Listo', 'Entregado', 'Cancelado')
    ),
    CONSTRAINT ck_historial_estado_nuevo CHECK (
        estado_nuevo IN ('Pendiente', 'Confirmado', 'En_preparacion', 'Listo', 'Entregado', 'Cancelado')
    )
);

CREATE INDEX idx_historial_pedido ON historial_estado_pedido (id_pedido);

COMMENT ON TABLE historial_estado_pedido IS 'RNF-09: usuario, fecha y hora, estado anterior y nuevo de cada cambio. Solo se inserta; estado_anterior es NULL al crear el pedido.';

CREATE OR REPLACE FUNCTION fn_historial_inmutable()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'historial_estado_pedido es inmutable (RNF-09): no se permite % ', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_historial_inmutable
    BEFORE UPDATE OR DELETE ON historial_estado_pedido
    FOR EACH ROW EXECUTE FUNCTION fn_historial_inmutable();

-- ============================================================
-- TABLA: rechazo_pedido
-- Intentos de pedido que no se pudieron aceptar por falta de existencias
-- Respalda la métrica propia "pedidos rechazados por falta de insumos"
-- ============================================================
CREATE TABLE rechazo_pedido (
    id_rechazo     SERIAL PRIMARY KEY,
    id_cliente     INT         NOT NULL,
    id_pedido      INT,
    motivo         VARCHAR(30) NOT NULL,
    fecha_rechazo  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_rechazo_cliente FOREIGN KEY (id_cliente)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT fk_rechazo_pedido FOREIGN KEY (id_pedido)
        REFERENCES pedido (id_pedido) ON DELETE RESTRICT,
    CONSTRAINT ck_rechazo_motivo CHECK (motivo IN ('Insumos_insuficientes', 'Stock_insuficiente'))
);

CREATE INDEX idx_rechazo_motivo ON rechazo_pedido (motivo);
CREATE INDEX idx_rechazo_fecha ON rechazo_pedido (fecha_rechazo);

COMMENT ON TABLE rechazo_pedido IS 'id_pedido es NULL si la validación falla antes de crear el pedido; tiene valor si falla al confirmarlo (el pedido queda Pendiente).';

COMMIT;

-- ============================================================
-- NOTAS PARA EL AGENTE DE IA / EQUIPO DE DESARROLLO
-- ============================================================
-- 1. Este esquema es la fuente de verdad. No crear columnas, tablas ni
--    relaciones adicionales sin antes consultarlo con el equipo.
-- 2. Los nombres de tabla están en snake_case para mapear directo a los
--    modelos de Django (Meta.db_table si se requiere nombre exacto).
--    Este SQL es la referencia de diseño: en el proyecto las tablas las crean
--    las migraciones de Django. No ejecutar este script además de las
--    migraciones. Los triggers no los genera Django: agregarlos en una
--    migración con RunSQL. En el modelo de usuario, mapear con db_column los
--    campos password y is_active hacia contrasena_hash y activo.
-- 3. Confirmar un pedido (pago simulado Exitoso, RNF-30) va en una sola
--    transacción atómica (transaction.atomic):
--      a. Bloquear el pedido (select_for_update) y verificar estado = Pendiente.
--      b. Por cada línea: si el producto es Disponible, validar y restar
--         stock_producto (origen = Stock, dias_produccion = 0); si es
--         Sobre_pedido, validar y descontar insumos según el BOM (origen =
--         Confeccion, dias_produccion = tiempo_produccion_dias) y registrar un
--         movimiento Descuento por insumo.
--      c. Si falta stock o insumos: revertir la transacción y registrar el
--         rechazo en rechazo_pedido fuera de la transacción revertida.
--      d. Calcular fecha_estimada_entrega (cola + tiempo propio), guardar
--         fecha_confirmacion y pago_simulado_estado = Exitoso, pasar el estado a
--         Confirmado e insertar la fila en historial_estado_pedido.
-- 4. Regla de cancelación: solo pedidos en Pendiente o Confirmado pueden pasar a
--    Cancelado; En_preparacion, Listo y Entregado no se pueden cancelar (el
--    trigger trg_pedido_transicion_estado lo exige). Cancelar va en una sola
--    transacción atómica:
--      a. Bloquear el pedido (select_for_update) para evitar dos cancelaciones
--         simultáneas.
--      b. Si estaba Confirmado: por cada movimiento Descuento del pedido insertar
--         un movimiento Devolucion con la misma cantidad y sumarla a
--         insumo.cantidad_disponible; por cada línea con origen = Stock sumar la
--         cantidad a producto.stock_producto. Nunca recalcular desde el BOM
--         actual: el BOM pudo cambiar después de confirmar.
--      c. Pasar el estado a Cancelado, guardar fecha_cancelacion e insertar la fila
--         en historial_estado_pedido.
-- 5. producto.stock_producto solo es relevante cuando tipo = Disponible. Para
--    Sobre_pedido la disponibilidad se valida contra insumo.
-- 6. Las alertas del Asistente PLUS se calculan con consultas al momento
--    (ADR-04), no requieren tabla propia. Ver consultas de apoyo abajo.
-- 7. La cola del Motor de Fecha (RNF-27) cuenta los pedidos en Confirmado y
--    En_preparacion; excluye Pendiente (sin pago), Listo, Entregado y Cancelado.
-- 8. El carrito no tiene tabla: se conserva en el almacenamiento del navegador
--    (RNF-18). Los pedidos se crean al iniciar el pago.
-- 9. Al crear el pedido se copian la dirección y el teléfono (del perfil o los
--    digitados en el checkout) a pedido.direccion_entrega y
--    pedido.telefono_contacto. Si el cliente no tiene esos datos en su perfil, el
--    checkout debe pedirlos antes de crear el pedido. Sigue fuera del alcance la
--    logística de envíos con transportadoras: son datos de contacto y entrega.
-- 10. La métrica "abandono de registro" no se resuelve con este esquema: medirla
--    con registros de la aplicación o dejarla fuera.
-- ============================================================

-- ============================================================
-- CONSULTAS DE APOYO (referencia; no forman parte del esquema)
-- ============================================================

-- Regla 1 PLUS: insumos en o por debajo del stock mínimo
-- SELECT id_insumo, nombre, cantidad_disponible, stock_minimo
--   FROM insumo
--  WHERE cantidad_disponible <= stock_minimo;

-- Regla 1 PLUS: productos Disponible en o por debajo del stock mínimo
-- SELECT id_producto, nombre, stock_producto, stock_minimo
--   FROM producto
--  WHERE activo AND tipo = 'Disponible' AND stock_producto <= stock_minimo;

-- Regla 2 PLUS: pedidos no terminados con entrega estimada en 2 días o menos
-- SELECT id_pedido, estado, fecha_estimada_entrega
--   FROM pedido
--  WHERE estado IN ('Confirmado', 'En_preparacion')
--    AND fecha_estimada_entrega <= CURRENT_DATE + 2;

-- Regla 3 PLUS: productos activos con menos de 3 unidades vendidas en 30 días
-- SELECT pr.id_producto, pr.nombre,
--        COALESCE(SUM(CASE WHEN pe.id_pedido IS NOT NULL THEN d.cantidad END), 0) AS ventas_30_dias
--   FROM producto pr
--   LEFT JOIN detalle_pedido d ON d.id_producto = pr.id_producto
--   LEFT JOIN pedido pe ON pe.id_pedido = d.id_pedido
--        AND pe.estado NOT IN ('Pendiente', 'Cancelado')
--        AND pe.fecha_confirmacion >= NOW() - INTERVAL '30 days'
--  WHERE pr.activo
--  GROUP BY pr.id_producto, pr.nombre
-- HAVING COALESCE(SUM(CASE WHEN pe.id_pedido IS NOT NULL THEN d.cantidad END), 0) < 3;

-- Motor de Fecha: días ya comprometidos en la cola
-- SELECT COALESCE(SUM(d.cantidad * d.dias_produccion), 0) AS dias_en_cola
--   FROM pedido p
--   JOIN detalle_pedido d ON d.id_pedido = p.id_pedido
--  WHERE p.estado IN ('Confirmado', 'En_preparacion');

-- Métrica: precisión de la fecha estimada (días de diferencia promedio)
-- SELECT AVG(ABS(fecha_entrega_real - fecha_estimada_entrega)) AS dias_error_promedio
--   FROM pedido
--  WHERE estado = 'Entregado';

-- Métrica: porcentaje de pedidos rechazados por falta de insumos
-- SELECT 100.0 * COUNT(*) FILTER (WHERE r.motivo = 'Insumos_insuficientes')
--        / NULLIF((SELECT COUNT(*) FROM pedido) + COUNT(*) FILTER (WHERE r.id_pedido IS NULL), 0)
--          AS pct_rechazados_por_insumos
--   FROM rechazo_pedido r;
