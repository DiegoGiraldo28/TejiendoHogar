# Guía de trabajo: TejiendoHogar

## Fase actual
Fase 2: gestión del catálogo para la Emprendedora, insumos, movimientos de entrada, recetas y panel; catálogo público y resumen provisional del pedido para el Cliente. La persistencia de pedidos, carrito, checkout y pago corresponden a la Fase 3.

## Apps y dependencias
- `apps.accounts`: usuarios y autenticación; no importa de apps nuevas.
- `apps.catalog`: productos y pantallas de gestión; puede importar `accounts`, nunca `inventory`.
- `apps.inventory`: insumos, recetas y movimientos; puede importar `accounts` y `catalog`.
- `apps.alerts`: panel; puede importar `accounts`, `catalog` e `inventory`.
- `apps.orders`: contiene únicamente el resumen POST provisional; no crea pedidos ni tiene modelos.
- `apps.legal`: páginas públicas estáticas de términos, privacidad y cookies; no tiene modelos ni depende de otras apps.

Evita dependencias cíclicas. Las tablas de dominio se crean mediante migraciones; `tejiendohogar_schema.sql` es referencia y nunca se ejecuta. No uses SQL crudo.

## Reglas de implementación
- Django Templates, ORM y formularios Django; CSRF activo.
- Servicios en `services.py`, con argumentos keyword-only, `full_clean()` y errores `ValidationError` en español.
- Control de acceso con `rol_requerido` y `RolRequeridoMixin` de `accounts.permissions`.
- Archivos de imagen sin Pillow: extensión, máximo de 2 MB y firma verificada en el modelo.
- Solo entradas modifican cantidades de insumos; siempre se guarda su movimiento.
- No añadir Django Admin, API REST, Node, npm ni dependencias fuera del stack acordado.
- Las páginas legales informan al usuario; antes de operar el servicio se completan los datos del responsable y el mecanismo de autorización de tratamiento.

## Rutas de Etapa A
- `/` (`inicio`) vive en `apps.catalog`: muestra la bienvenida al anónimo y redirige por rol a quien tenga sesión.
- `/panel/`
- `/emprendedora/productos/`, `/emprendedora/productos/nuevo/`, `/<id>/editar/`, `/<id>/estado/`, `/<id>/eliminar/`
- `/emprendedora/productos/<id>/receta/`
- `/emprendedora/insumos/`, `/emprendedora/insumos/nuevo/`, `/<id>/editar/`, `/<id>/entrada/`, `/<id>/movimientos/`, `/<id>/eliminar/`
- `/catalogo/`, `/catalogo/<id>/`
- `POST /pedidos/en-proceso/` para Cliente autenticado.

## Pruebas y ejecución
Desde `backend/`, usa `python manage.py check`, `python manage.py makemigrations`, `python manage.py migrate`, `python manage.py cargar_datos_demo` y `pytest --cov=apps.accounts --cov=apps.catalog --cov=apps.inventory --cov=apps.alerts --cov=apps.orders --cov-report=term-missing --cov-fail-under=80`.

## Decisiones y pendientes
- Por dependencia de la tabla `pedido`, `MovimientoInsumo.id_pedido` y su CHECK se incorporan en la Fase 3.
- La Fase 3 agrega `id_pedido`, integra pedidos con `validar_disponibilidad` y `calcular_requerimiento`, y reemplaza el resumen provisional por carrito, checkout y pago.
- No hacer commits automáticamente ni incluir secretos en el repositorio.
