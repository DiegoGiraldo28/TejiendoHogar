# Reporte de corrección de auditoría TejiendoHogar

Rama: `fix/TEJ-XX-incidencias-codigo` (creada desde `main`). No se hicieron commits.

## Incidencias

| ID / tema | Archivos principales | Verificación | Estado |
|---|---|---|---|
| U-01, U-03, U-04, U-06, A1–A6: registro, login, intentos y validación de contraseña | `backend/apps/accounts/`, `backend/apps/common/`, `backend/config/settings/base.py`, `frontend/templates/accounts/`, `frontend/static/js/validacion.js` | `apps/accounts/tests/test_accounts.py` y `apps/common/test_common.py` | Corregida |
| A-03, B-08: disponibilidad Sobre pedido y máximo 10 | `backend/apps/orders/`, `backend/apps/inventory/templatetags/inventario.py`, `frontend/templates/catalog/detalle.html` | `apps/orders/tests/test_orders.py`, `apps/catalog/tests/test_catalog_public.py` | Corregida |
| B-04, A-09: validadores numéricos, restricciones y búsqueda sin tildes | `backend/apps/catalog/`, `backend/apps/inventory/`, `backend/apps/accounts/`, migraciones | `apps/catalog/tests/`, `apps/inventory/tests/`, `apps/accounts/tests/` | Corregida |
| A-02: dimensiones mínimas de imagen | `backend/apps/catalog/`, `backend/apps/inventory/management/commands/cargar_datos_demo.py`, `backend/conftest.py` | pruebas de imagen PNG/JPEG/WEBP en `apps/accounts/tests/test_accounts.py` | Corregida |
| B6: creación de producto, receta obligatoria y formularios accesibles | `backend/apps/catalog/`, `backend/apps/inventory/`, `frontend/templates/catalog/`, `frontend/templates/inventory/`, `frontend/static/js/catalogo.js` | `apps/catalog/tests/test_catalog.py`, `apps/catalog/tests/test_catalog_public.py`, `apps/inventory/tests/test_inventory.py` | Corregida |
| C1, D-08: estilo Python en CI | `.github/workflows/ci.yml`, `backend/setup.cfg`, `backend/requirements/dev.txt`, fuentes Python | `pycodestyle apps config` | Corregida para el código permitido; `prod.py` queda fuera por la prohibición de editarlo |
| C2–C5: capas, duplicados, enumeraciones, anotaciones y docstrings | `backend/apps/common/`, servicios y vistas de `accounts`, `catalog`, `inventory` | suite completa y `manage.py check` | Corregida |
| C6–C8: código muerto, clave secreta y fixtures compartidas | `backend/config/settings/base.py`, `dev.py`, `backend/conftest.py`, plantillas y CSS | suite completa y revisión de referencias | Corregida |
| D1: datos del responsable legal | `frontend/templates/legal/` | `apps/legal/tests/test_views.py` | Corregida |
| Requisitos de despliegue que no pueden cambiarse aquí | `.ebextensions/`, `.platform/`, `Procfile`, requisitos de producción, `prod.py`, sección de despliegue del README | inspección de archivos modificados | Pendiente para el trabajo de despliegue |

## Pruebas

| Ejecución | Resultado |
|---|---|
| Línea base, antes de los cambios | 109 pruebas recogidas; 4 pasaron y 105 no pudieron ejecutarse por denegación de acceso al PostgreSQL local en el entorno no elevado. Cobertura agregada reportada: 40%; no se considera una línea base fiable por los errores de infraestructura. |
| Final: `pytest --cov=apps --cov-report=term` | 134 pasaron; cobertura total 96%. |
| `manage.py check` | Sin problemas. |
| `manage.py makemigrations --check --dry-run` | No hay cambios pendientes. |
| `pycodestyle apps config` | 0 infracciones en el alcance verificado. `prod.py` se excluye deliberadamente, sin editar, porque está prohibido modificarlo. |

Cobertura por app: accounts 98.5%, alerts 100%, catalog 95.2%, inventory 92.8%, legal 100%, orders 100%. `apps.common` no es una app instalada; sus ayudantes tienen pruebas propias y quedaron al 100%.

### Pruebas renombradas, modificadas o eliminadas

- Renombrada `test_registro_muestra_orden_ayuda_legal_y_telefono_visible` → `test_registro_muestra_ayudas_y_atributos_de_validacion`.
- Reemplazada `test_registro_emprendedora_se_rechaza_sin_crear` → `test_registro_no_muestra_selector_y_crea_cliente`; se añadió `test_registro_ignora_perfil_enviado_por_post`.
- Renombrada `test_selector_no_coincidente_no_autentica` → `test_rol_sin_acceso_web_usa_mensaje_generico_y_no_autentica`.
- Renombrada `test_listado_publico_filtra_activos_busqueda_tipo_y_pagina` → `test_listado_publico_filtra_activos_busqueda_y_tipo`.
- Renombrada `test_politica_privacidad_identifica_placeholders_de_responsable` → `test_paginas_legales_muestran_datos_del_responsable`.
- Modificada `test_producto_sobre_pedido_redirige_y_guarda_receta_en_flujo_completo` para comprobar el flujo de receta y redirección actualizado.
- Añadidas pruebas para bloqueo y reinicio de intentos, reglas de contraseña, teléfono inválido, imágenes y dimensiones en los tres formatos, búsqueda con tildes, stock y receta, disponibilidad de pedido, límite de 10 y datos legales compartidos.
- Se consolidaron fixtures de producto, imagen y `media_temporal` en `backend/conftest.py`; se eliminaron las copias locales de `apps/catalog/tests/conftest.py` y `apps/orders/tests/conftest.py`.

## Migraciones y SQL generado

`sqlmigrate` se ejecutó en las cuatro migraciones nuevas. No hay eliminaciones o renombres de tablas/columnas ni alteraciones de datos.

| Migración | Clasificación y SQL relevante |
|---|---|
| `accounts 0002_intentoacceso_alter_usuario_ck_usuario_rol_and_more` | **Crea tabla** `intento_acceso` con `id`, `correo`, `fecha`, `exitoso`; crea índice `idx_intento_correo_fecha`. Alteraciones de restricciones existentes: `(no-op)`. |
| `catalog 0002_alter_producto_precio_alter_producto_stock_minimo_and_more` | **Solo estado de Django (sin SQL)** para validadores y mensajes; las restricciones informan `(no-op)`. |
| `catalog 0003_unaccent_extension` | **Crea extensión**: `CREATE EXTENSION IF NOT EXISTS "unaccent";` |
| `inventory 0002_alter_insumo_cantidad_disponible_and_more` | **Solo estado de Django (sin SQL)** para validadores y mensajes; las restricciones informan `(no-op)`. |

La extensión `unaccent` se crea al aplicar la migración en el entorno de despliegue; en RDS requiere usuario maestro.

### Migración accounts regenerada

Antes de aplicarse fuera del entorno local, se regeneró `accounts 0002` con `IntentoAcceso.Meta.db_table = "intento_acceso"` para seguir la convención del esquema. `sqlmigrate` ahora produce:

```sql
CREATE TABLE "intento_acceso" (
    "id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY,
    "correo" varchar(150) NOT NULL,
    "fecha" timestamp with time zone NOT NULL,
    "exitoso" boolean NOT NULL
);
CREATE INDEX "idx_intento_correo_fecha"
    ON "intento_acceso" ("correo", "exitoso", "fecha");
```

Las tres alteraciones de restricciones de `usuario` que aparecen en esa migración son `(no-op)` en PostgreSQL.

## Reutilización

- Se conservaron y llamaron los servicios existentes `registrar_cliente`, `destino_rol`, `validar_disponibilidad`, `unidades_fabricables`, `calcular_requerimiento` y `guardar_receta`.
- Se consolidó la validación telefónica y el traspaso de errores a formularios en `apps.common.validators` y `apps.common.forms`.
- Se reutilizó el parcial común `partials/_field.html`; se eliminaron los parciales duplicados del área de cuentas.
- Se centralizaron constantes de imágenes, paginación y límite de unidades en `apps.common.constants`.
- Se agruparon helpers y fixtures de imágenes/productos en `backend/conftest.py`.
- Se unificaron los datos legales en `legal/_responsable.html` y el filtro de texto de búsqueda usa la misma expresión `nombre__unaccent__icontains` en catálogo e inventario.

## Aclaraciones solicitadas

- **C6, ruta `/emprendedora/`:** se conservó la URL y `PaginaEmprendedoraView`, que hereda `RolRequeridoMixin` y redirige al panel. La ruta sigue referenciada por `test_raiz_y_paginas_correctas` y por las pruebas de acceso por rol; eliminarla habría cambiado comportamiento observable.
- **C7, `SECRET_KEY` en CI:** sí. `.github/workflows/ci.yml` define `SECRET_KEY: ci-test-secret` en el entorno del job. `backend/requirements/dev.txt` solo agrega `pycodestyle>=2.11,<3.0`; las otras dependencias ya estaban.
- **Pruebas de dimensiones:** están en `backend/apps/catalog/tests/test_catalog.py`: `test_imagen_de_200_por_200_se_acepta_en_todos_los_formatos` y `test_imagen_menor_a_200_por_200_se_rechaza`. Por tanto, ya están en la app correspondiente y no hizo falta moverlas.
- **Paginación del catálogo público:** la verifica `test_catalogo_pagina_en_lotes_de_doce` en `backend/apps/catalog/tests/test_catalog_public.py`, usando solicitudes a la vista para la primera página y `?page=2`.

## Supuestos y límites

- Se mantuvo sin cambios `backend/config/settings/prod.py`, aunque sus infracciones previas de pycodestyle quedan fuera del alcance. El archivo se excluye de esa comprobación hasta el trabajo de despliegue.
- No se ejecutó `cargar_datos_demo` ni se hizo una pasada visual manual en navegador; los comportamientos de aplicación se verificaron mediante PyTest. La revisión visual manual solicitada queda pendiente.
- `git diff --check` señala un espacio final preexistente en `AGENTS.md:93`; el archivo es guía proporcionada por el usuario y se dejó intacto.
- `AGENTS.md` aparece modificado y `Estudiantes.md` eliminado por cambios previos del usuario; no forman parte de esta corrección. Se conservó la eliminación solicitada de `.vscode/settings.json` del índice y se agregó `.vscode/` a `.gitignore`.
- La línea base no fue fiable porque el primer intento no tuvo acceso al PostgreSQL local. El resultado final se ejecutó con el acceso requerido y terminó correctamente.

## Mensajes de commit sugeridos por fase

- Fase A: `TEJ-XX: corrige autenticación y validación de cuentas`
- Fase B: `TEJ-XX: corrige catálogo, recetas y disponibilidad de pedidos`
- Fase C: `TEJ-XX: mejora calidad y elimina duplicación de código`
- Fase D: `TEJ-XX: centraliza los datos legales del responsable`
