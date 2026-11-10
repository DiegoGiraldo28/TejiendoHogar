# Guía de trabajo: TejiendoHogar

## Fase actual
Fase 2: gestión del catálogo para la Emprendedora, insumos, movimientos de entrada, recetas y panel; catálogo público y resumen provisional del pedido para el Cliente. En curso: corrección de las incidencias de la auditoría externa (rama `fix/TEJ-XX-incidencias-codigo`). La persistencia de pedidos, el carrito, el checkout y el pago corresponden a la Fase 3.

Este archivo describe el **estado objetivo** de la corrección. Si el código todavía no cumple una regla de esta guía, la regla manda y el código se ajusta a ella.

## Stack
Django 5.2, PostgreSQL, Django Templates, CSS y JavaScript puros, PyTest. No se agregan dependencias (ni django-axes, ni Pillow, ni factory_boy, ni DRF, ni Node/npm). `django.contrib.postgres` está permitido porque es parte de Django.

## Apps y dependencias
| Paquete | Puede importar de | Notas |
|---|---|---|
| `apps.common` | ninguna app | Paquete, **no app**: no va en `INSTALLED_APPS` ni tiene modelos ni migraciones. `validators.py` (teléfono) y `forms.py` (`agregar_errores`). |
| `apps.accounts` | `common` | Usuarios, autenticación y modelo `IntentoAcceso`. |
| `apps.catalog` | `accounts`, `common` | **Nunca importa `inventory` en Python.** En plantillas puede usar `{% load inventario %}`. Redirigir por nombre de URL (`inventory:receta`) no es una importación. |
| `apps.inventory` | `accounts`, `catalog`, `common` | Insumos, recetas y movimientos. Define el template tag `unidades_fabricables` en `templatetags/inventario.py`. |
| `apps.alerts` | `accounts`, `catalog`, `inventory`, `common` | Panel de la Emprendedora. |
| `apps.orders` | `accounts`, `catalog`, `inventory`, `common` | Solo el resumen POST provisional; no crea pedidos ni tiene modelos. Valida la disponibilidad con `validar_disponibilidad`. |
| `apps.legal` | ninguna | Páginas estáticas de términos, privacidad y cookies; sin modelos. |

Evita dependencias cíclicas. Las tablas de dominio se crean mediante migraciones; `tejiendohogar_schema.sql` es una referencia y nunca se ejecuta. No uses SQL crudo.

## Autenticación y roles
- **Registro público:** crea exclusivamente cuentas de Cliente, sin selector de perfil. Si llega un campo `perfil` por POST, se ignora. `registrar_cliente` fija el rol y ningún dato del formulario puede cambiarlo. Las cuentas de Emprendedora las habilita la administración.
- **Login sin selector:** valida las credenciales, toma el rol de la base de datos y redirige con `destino_rol` (Emprendedora → `/panel/`, Cliente → `/catalogo/`).
- **Mensaje único de error:** «Correo o contraseña incorrectos.». Se usa para credenciales inválidas y para roles sin acceso web (Operaria); en ese caso no se crea sesión.
- **Intentos de acceso:** se registran en el modelo `IntentoAcceso` (correo normalizado, fecha, `exitoso`) y cada fallo se escribe con `logger.warning`. Con 5 fallos en 15 minutos para el mismo correo se bloquea 15 minutos con «Demasiados intentos. Intenta de nuevo en 15 minutos.». Un inicio de sesión exitoso reinicia el conteo. No se usa la caché de Django.
- **Contraseñas:** `validate_password` siempre recibe una usuaria (en el registro, un `Usuario` sin guardar con nombre y correo). `UserAttributeSimilarityValidator` usa `user_attributes = ("nombre", "correo")`.

## Reglas de negocio
- **Valores numéricos:** `PRECIO_MINIMO = 0`; días de producción ≥ 1; stock y stock mínimo ≥ 0. Cada `CheckConstraint` tiene `violation_error_message` en español.
- **Productos Disponible:** usan `stock_producto` y `stock_minimo`.
- **Productos Sobre pedido:** su stock es 0. Se crean inactivos y la receta es el paso obligatorio inmediato. No se activan sin receta. La receta solo usa insumos registrados en Insumos.
- **Regla A-03:** un Sobre pedido con 0 unidades fabricables sigue visible, muestra «Sin insumos por ahora» y deshabilita «Hacer pedido». El servidor valida la disponibilidad al recibir el pedido.
- **`MAX_UNIDADES_SOBRE_PEDIDO = 10`:** se define en un solo lugar y se usa en el formulario y en la plantilla.
- **Insumos:** solo las entradas modifican cantidades y siempre se guarda su movimiento.
- **Imágenes (sin Pillow):** JPG, PNG o WEBP; máximo 2 MB (constante única); firma verificada; mínimo 200 × 200 px, leídos de la cabecera del archivo.
- **Búsquedas:** usan `nombre__unaccent__icontains`. La extensión `unaccent` se crea por migración en `catalog`.

## Reglas de implementación
- Django Templates, ORM y formularios Django; CSRF activo.
- **Servicios** (`services.py`): argumentos keyword-only, anotaciones de tipo, `full_clean()` y `ValidationError` en español. Devuelven querysets u objetos; no lanzan `Http404` ni paginan.
- **Vistas:** paginan (tamaño de página en una constante) y responden el 404. Las vistas de registro, login y perfil tienen docstring.
- **Código compartido:** los errores de servicio pasan al formulario con `apps.common.forms.agregar_errores`; el teléfono se valida con `apps.common.validators`. No dupliques ese código.
- **Enumeraciones:** `Rol.values` y `Tipo.values` en las restricciones; `Rol.choices` y `Tipo.choices` en los formularios. JavaScript recibe esos valores desde la plantilla con atributos `data-`.
- **Control de acceso:** `rol_requerido` y `RolRequeridoMixin` de `accounts.permissions`.
- **Plantillas:** un solo parcial, `partials/_field.html`. Las reglas se ven antes de enviar (textos de ayuda) y los atributos HTML (`inputmode`, `pattern`, `min`, `max`, `minlength`, `maxlength`) equivalen a los validadores del servidor. Ningún error puede quedar dentro de un elemento oculto.
- **JavaScript:**
  - `validacion.js` hace la validación en vivo (`blur` e `input`, `checkValidity`, `aria-invalid`, `aria-describedby`) y se carga solo en las plantillas que lo usan.
  - Sin JavaScript todo funciona y el servidor valida siempre.
  - `data-toggle-password` va solo en el botón que lee `auth.js`.
  - Un campo que el JS oculta o deshabilita no puede volver obligatorio el formulario.
- **Estilo:** PEP 8 con un máximo de 120 caracteres por línea. `pycodestyle` se configura en `backend/setup.cfg` (excluye `migrations`), debe quedar en 0 infracciones y corre en el CI.
- **`SECRET_KEY`:** sin valor de respaldo en `base.py`; `dev.py` define la de desarrollo y `prod.py` la exige como variable.
- No añadir Django Admin, API REST, Node, npm ni dependencias fuera del stack.

## Páginas legales
- Responsable: **Equipo TejiendoHogar** · NIT: **900.123.456-7 (ficticio, con fines académicos)** · Correo: **diegoh.giraldoc@uqvirtual.edu.co**.
- Estos datos se definen una sola vez en el parcial `legal/_responsable.html` y se usan en las tres páginas.
- Antes de operar comercialmente, se reemplaza el NIT ficticio y se implementa el mecanismo de autorización de tratamiento de datos.

## Rutas
- `/` (`inicio`) vive en `apps.catalog`: muestra la bienvenida al anónimo y redirige por rol a quien tenga sesión.
- `/panel/`
- `/emprendedora/productos/`, `/emprendedora/productos/nuevo/`, `/<id>/editar/`, `/<id>/estado/`, `/<id>/eliminar/`
- `/emprendedora/productos/<id>/receta/`
- `/emprendedora/insumos/`, `/emprendedora/insumos/nuevo/`, `/<id>/editar/`, `/<id>/entrada/`, `/<id>/movimientos/`, `/<id>/eliminar/`
- `/catalogo/`, `/catalogo/<id>/`
- `POST /pedidos/en-proceso/` para Cliente autenticado.

## Pruebas y ejecución
- Desde `backend/`:
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
  - `python manage.py migrate`
  - `python manage.py cargar_datos_demo`
  - `pytest --cov=apps --cov-report=term-missing`
  - `pycodestyle apps config`
- La cobertura debe ser ≥ 80 % por app.
- Los ayudantes compartidos viven en `backend/conftest.py`: `media_temporal`, creación de productos e imágenes PNG válidas de al menos 200 × 200 px (generadas con `zlib` y `struct`). No los dupliques en las apps.
- Los nombres de las pruebas aparecen en el documento de pruebas: toda prueba renombrada, modificada o eliminada se reporta con su nombre anterior y el nuevo.

## Archivos de despliegue
`.ebextensions/`, `.platform/`, `Procfile`, `requirements.txt` de la raíz, `backend/requirements/prod.txt`, `backend/config/settings/prod.py` y la sección de despliegue del README se modifican **solo** en los trabajos de despliegue. Si una corrección de código los necesita, se anota como «pendiente para el trabajo de despliegue».

## Decisiones y pendientes
- **SonarQube (D-08):** no se integra; se usan pycodestyle en el CI y la cobertura de PyTest.
- **Migración `unaccent`:** crea la extensión al desplegar; en RDS requiere el usuario maestro.
- **Fase 3:**
  - Por la dependencia de la tabla `pedido`, `MovimientoInsumo.id_pedido` y su CHECK se incorporan en esta fase.
  - Se agrega `id_pedido`, se integran los pedidos con `validar_disponibilidad` y `calcular_requerimiento`, y el resumen provisional se reemplaza por carrito, checkout y pago.
- No hacer commits automáticamente ni incluir secretos en el repositorio.    