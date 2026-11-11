# Guía de trabajo: TejiendoHogar

## Fase actual
Fase 3: pedidos con pago simulado (rama `feature/TEJ-XX-proceso-pedidos`).
- La Cliente tiene bolsa, datos de entrega, pago simulado, fecha estimada, «Mis pedidos» y seguimiento.
- La Emprendedora gestiona los pedidos: cambia su estado y los cancela con devolución.
- El stock y los insumos se descuentan al confirmar.

La Fase 2 (catálogo, insumos, recetas y panel) y las correcciones de la auditoría externa siguen vigentes.

## Fuentes de referencia
- **Esquema:** `docs/tejiendohogar_schema1.sql`. Es la referencia de tablas, restricciones, triggers y notas; nunca se ejecuta.
- **Mockups:** tres carpetas en la raíz del repositorio. Sus nombres de archivo tienen espacios y tildes, así que van entre comillas.
  - `MockupsClienteMovil/`: catálogo, detalle, bolsa, pago y seguimiento en móvil.
  - `MockupsClienteWebPC/`: bolsa, pago, seguimiento y perfil en PC.
  - `MockupEmprendedoraGestionPedidos/`: gestión de pedidos en PC.

Este archivo describe el **estado objetivo** de la corrección. Si el código todavía no cumple una regla de esta guía, la regla manda y el código se ajusta a ella.

## Stack
Django 5.2, PostgreSQL, Django Templates, CSS y JavaScript puros, PyTest. No se agregan dependencias (ni django-axes, ni Pillow, ni factory_boy, ni DRF, ni Node/npm). `django.contrib.postgres` está permitido porque es parte de Django.

## Apps y dependencias
| Paquete | Puede importar de | Notas |
|---|---|---|
| `apps.common` | ninguna app | Paquete, **no app**: no va en `INSTALLED_APPS` ni tiene modelos, migraciones ni template tags. `validators.py` (teléfono), `forms.py` (`agregar_errores`), `constants.py` y `formato.py` (`formatear_precio`). |
| `apps.accounts` | `common` | Usuarios, autenticación y modelo `IntentoAcceso`. El perfil usa una plantilla por rol: `perfil.html` (Cliente) y `perfil_emprendedora.html`. Esta última usa `{% load pedidos %}` (`piezas_entregadas`) sin importar `orders` en Python. |
| `apps.catalog` | `accounts`, `common` | **Nunca importa `inventory` ni `orders` en Python.** En plantillas puede usar `{% load inventario %}`. Redirigir por nombre de URL (`inventory:receta`, `orders:bolsa_agregar`) no es una importación. Define el filtro `precio` en `templatetags/precios.py`. |
| `apps.inventory` | `accounts`, `catalog`, `common` | Insumos, recetas y movimientos. Define el template tag `unidades_fabricables` en `templatetags/inventario.py`. Referencia `Pedido` **solo como texto** (`"orders.Pedido"`) en `MovimientoInsumo.pedido`. Registra los movimientos `Descuento` y `Devolucion` con `descontar_insumos` y `devolver_insumos`. `cargar_datos_demo` llama a `cargar_pedidos_demo` por nombre con `call_command`. |
| `apps.alerts` | `accounts`, `catalog`, `inventory`, `common` | Panel de la Emprendedora. |
| `apps.orders` | `accounts`, `catalog`, `inventory`, `common` | Modelos `Pedido`, `DetallePedido`, `HistorialEstadoPedido` y `RechazoPedido`. Bolsa en sesión (`carrito.py`), pasarela (`pagos.py`) y reglas en `services.py`. Vistas de la Cliente en `views.py` y de la Emprendedora en `views_emprendedora.py`. Template tag `piezas_entregadas` en `templatetags/pedidos.py`. Crea pedidos y valida con `validar_disponibilidad` y `calcular_requerimiento`. |
| `apps.legal` | ninguna | Páginas estáticas de términos, privacidad y cookies; sin modelos. |

Evita dependencias cíclicas. Las tablas de dominio se crean mediante migraciones; `docs/tejiendohogar_schema1.sql` es una referencia y nunca se ejecuta. No uses SQL crudo. La **única excepción** es `orders/migrations/0002_triggers.py`, que crea con `RunSQL` y su `reverse_sql` los triggers `fn_validar_transicion_pedido` y `fn_historial_inmutable` del esquema.

## Autenticación y roles
- **Registro público:** crea exclusivamente cuentas de Cliente, sin selector de perfil. Si llega un campo `perfil` por POST, se ignora. `registrar_cliente` fija el rol y ningún dato del formulario puede cambiarlo. Las cuentas de Emprendedora las habilita la administración.
- **Login sin selector:** valida las credenciales, toma el rol de la base de datos y redirige con `destino_rol` (Emprendedora → `/panel/`, Cliente → `/catalogo/`).
- **Mensaje único de error:** «Correo o contraseña incorrectos.». Se usa para credenciales inválidas y para roles sin acceso web (Operaria); en ese caso no se crea sesión.
- **Intentos de acceso:** se registran en el modelo `IntentoAcceso` (correo normalizado, fecha, `exitoso`) y cada fallo se escribe con `logger.warning`. Con 5 fallos en 15 minutos para el mismo correo se bloquea 15 minutos con «Demasiados intentos. Intenta de nuevo en 15 minutos.». Un inicio de sesión exitoso reinicia el conteo. No se usa la caché de Django.
- **Contraseñas:** `validate_password` siempre recibe una usuaria (en el registro, un `Usuario` sin guardar con nombre y correo). `UserAttributeSimilarityValidator` usa `user_attributes = ("nombre", "correo")`.

## Reglas de negocio
- **Valores numéricos:** `PRECIO_MINIMO = 0`; días de producción ≥ 1; stock y stock mínimo ≥ 0. Cada `CheckConstraint` tiene `violation_error_message` en español.
- **Productos Disponible:** usan `stock_producto` y `stock_minimo`. No tienen días de confección: el formulario oculta y deshabilita el campo, y el servidor guarda `DIAS_PRODUCCION_DISPONIBLE = 1` para cumplir `ck_producto_tiempo_produccion`.
- **Productos Sobre pedido:** su stock es 0. Se crean inactivos y la receta es el paso obligatorio inmediato. No se activan sin receta. La receta solo usa insumos registrados en Insumos. Los días de confección son obligatorios y solo se muestran en estos productos.
- **Regla A-03:** un Sobre pedido con 0 unidades fabricables sigue visible, muestra «Sin insumos por ahora» y deshabilita «Comprar ahora» y «Agregar a la bolsa». El servidor valida la disponibilidad al crear y al confirmar el pedido.
- **`MAX_UNIDADES_SOBRE_PEDIDO = 10`:** se define en un solo lugar y se usa en el formulario, la bolsa y la plantilla. Un Disponible admite hasta su stock.
- **Insumos:** las entradas suman cantidades. Confirmar un pedido descuenta (`Descuento`) y cancelar un Confirmado devuelve (`Devolucion`). Siempre se guarda el movimiento, y los de pedido llevan `id_pedido`.
- **Precios:** se muestran siempre con el filtro `precio` («$89.000 COP»).

## Pedidos (Fase 3)
- **Flujo en 3 pasos (RNF-13):** 1) Bolsa y envío (`/carrito/`); 2) Simular pago (`/pedidos/<id>/pago/`); 3) Entrega (seguimiento). El paso 2 solo se marca hecho con pago Exitoso.
- **Bolsa:**
  - Vive en la sesión del servidor y solo la tiene la Cliente. Se conserva al cerrar el navegador y se vacía al cerrar sesión.
  - Los precios se recalculan siempre en el servidor. El precio de cada línea se congela al crear el Pendiente.
  - Dirección y teléfono son obligatorios y se precargan del perfil.
- **Pasarela intercambiable:**
  - `orders/pagos.py` define `PasarelaPago` (ABC) y `PasarelaSimulada`.
  - `obtener_pasarela()` lee `PASARELA_PAGO = "simulada"` en `config/settings/base.py`. Una pasarela real, por ejemplo Mercado Pago, se agrega como otra subclase sin tocar las vistas.
  - No se piden ni se guardan datos de tarjeta o cuenta, ni el método elegido. No existe «Pago contra entrega».
- **Momento del descuento:**
  - Crear el Pendiente solo valida la disponibilidad; no reserva ni descuenta.
  - `pagar_y_confirmar` hace todo en una transacción: bloquea el pedido con `select_for_update`, después productos e insumos en orden de llave primaria, revalida, cobra y, solo si el pago es Exitoso, descuenta el stock (origen `Stock`) o los insumos (origen `Confeccion`) y confirma.
  - Un doble envío lanza `PedidoYaConfirmado` y no descuenta dos veces.
  - Un rechazo guarda `RechazoPedido` fuera del bloque revertido.
- **Motor de fecha (RNF-27):**
  - Fecha estimada = día de confirmación + cola + días propios + `DIAS_ALISTAMIENTO` (1), en días calendario.
  - La cola es la suma de cantidad × `dias_produccion` de los pedidos Confirmados y En preparación. Los días propios son la suma de cantidad × `tiempo_produccion_dias` de los Sobre pedido; los Disponibles aportan 0.
  - Antes de pagar se muestra como estimación y se fija al confirmar. `desglose_fecha_entrega` reconstruye el cálculo desde lo guardado; devuelve `None` si el pedido no se ha confirmado.
- **Estados:**
  - Solo se avanza Confirmado → En preparación → Listo → Entregado, en el servicio y con el trigger.
  - Cada cambio queda en `HistorialEstadoPedido`, que es inmutable (RNF-09).
  - Nombre de `En_preparacion`, igual para la Cliente y la Emprendedora y con un solo ayudante (`orders.models.nombre_estado` y `Pedido.nombre_de_estado`):
    - «En confección» si alguna línea se confecciona (pedido mixto incluido). Antes de confirmar decide el tipo de producto (Sobre pedido); después, el origen guardado (`Confeccion`).
    - «En preparación» si todo sale del stock.
    - Se usa en las pastillas, el panel, la línea de estados y «Avanzar a "…"». El filtro agrupa ambos: «En preparación / confección (N)».
  - Los demás estados: la Emprendedora ve los nombres de la BD; la Cliente ve Pendiente = «En espera de pago» y Listo = «Listo y empaque».
- **Cancelación:**
  - La Cliente cancela solo sus pedidos Pendientes.
  - La Emprendedora cancela Pendientes o Confirmados.
  - En preparación, Listo y Entregado ya no se cancelan.
  - Cancelar un Confirmado devuelve el stock de las líneas `Stock` e insumos según los movimientos `Descuento` del pedido; nunca recalcula desde la receta actual.
- **Número visible:** `#TH-` + `id_pedido` con 4 dígitos; no se guarda.
- **Imágenes (sin Pillow):** JPG, PNG o WEBP; máximo 2 MB (constante única); firma verificada; mínimo 200 × 200 px, leídos de la cabecera del archivo.
- **Búsquedas:** usan `nombre__unaccent__icontains`. La extensión `unaccent` se crea por migración en `catalog`.

## Reglas de implementación
- Django Templates, ORM y formularios Django; CSRF activo.
- **Servicios** (`services.py`): argumentos keyword-only, anotaciones de tipo, `full_clean()` y `ValidationError` en español. Devuelven querysets u objetos; no lanzan `Http404` ni paginan.
- **Vistas:** paginan (tamaño de página en una constante) y responden el 404. Las vistas de registro, login y perfil tienen docstring.
- **Código compartido:** los errores de servicio pasan al formulario con `apps.common.forms.agregar_errores`; el teléfono se valida con `apps.common.validators`. No dupliques ese código.
- **Enumeraciones:** `Rol.values` y `Tipo.values` en las restricciones; `Rol.choices` y `Tipo.choices` en los formularios. JavaScript recibe esos valores desde la plantilla con atributos `data-`.
- **Control de acceso:** `rol_requerido` y `RolRequeridoMixin` de `accounts.permissions`.
- **Plantillas:** un solo parcial de campos, `partials/_field.html`. Los otros parciales son de presentación: `partials/_paginacion.html`, `catalog/_tarjeta_producto.html` y `orders/_pasos.html` (indicador de los 3 pasos). Las confirmaciones usan un único enlace `data-confirm-link`, que `confirmar.js` convierte en `<dialog>`; sin JavaScript lleva a una página de confirmación. Las reglas se ven antes de enviar (textos de ayuda) y los atributos HTML (`inputmode`, `pattern`, `min`, `max`, `minlength`, `maxlength`) equivalen a los validadores del servidor. Ningún error puede quedar dentro de un elemento oculto.
- **JavaScript:**
  - `validacion.js` hace la validación en vivo (`blur` e `input`, `checkValidity`, `aria-invalid`, `aria-describedby`) y se carga solo en las plantillas que lo usan.
  - Sin JavaScript todo funciona y el servidor valida siempre.
  - `data-toggle-password` va solo en el botón que lee `auth.js`.
  - Un campo que el JS oculta o deshabilita no puede volver obligatorio el formulario.
- **CSS:**
  - Colores siempre desde `variables.css`; el tono de error es `--error` / `--error-suave`.
  - `.secondary-button`, `.danger-button`, `.text-button`, `.button-link` y `.confirm-dialog` viven en `base.css` y sirven a todas las pantallas. `.primary-button` está en `accounts.css`, con el ajuste de `catalog.css`.
  - El atributo `hidden` siempre oculta (`[hidden]{display:none !important}`).
  - Las acciones dentro de filas (`.table-actions` de Insumos y `.low-stock-list` del panel) se ven como enlaces. Allí «Eliminar…» es un `danger-button` compacto; las reglas acotadas de `inventory.css` ganan por especificidad a las de `base.css`.
  - Al cambiar un CSS que una plantilla carga con `?v=…`, se sube esa versión.
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
- `/emprendedora/pedidos/`, `/emprendedora/pedidos/<id>/` (maestro-detalle), `POST /<id>/avanzar/`, `/<id>/cancelar/` (GET confirma, POST cancela): Emprendedora.
- `/catalogo/`, `/catalogo/<id>/`
- Cliente:
  - `/carrito/` (bolsa) y `POST /carrito/agregar/<id>/`. Un visitante va al login con `next` = detalle del producto.
  - `/pedidos/<id>/pago/`.
  - `/mis-pedidos/`, `/mis-pedidos/<id>/` (seguimiento) y `/mis-pedidos/<id>/cancelar/`.
- `/pedidos/en-proceso/` (antigua página provisional) redirige a `/carrito/`.

## Pruebas y ejecución
- Desde `backend/`:
  - `python manage.py check`
  - `python manage.py makemigrations --check --dry-run`
  - `python manage.py migrate`
  - `python manage.py cargar_datos_demo` (también crea 4 pedidos de ejemplo para la primera Cliente que exista; no crea usuarios)
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
- **Fase 3 (hecha):**
  - `MovimientoInsumo.id_pedido` y `ck_movimiento_pedido` se incorporaron en `inventory/0003`.
  - El resumen provisional se reemplazó por bolsa, checkout y pago simulado.
- **Pendiente de documentación:** actualizar la nota 8 del esquema y el RNF-18 (la bolsa vive en la sesión del servidor, no en el navegador).
- **Limitación conocida:** dos confirmaciones simultáneas de productos distintos pueden calcular la misma cola en el motor de fecha. El inventario no se ve afectado.
- **Seguimiento local:** `PROGRESO_PEDIDOS.md` y `REPORTE_PEDIDOS.md` están en `.gitignore` y no se versionan.
- No hacer commits automáticamente ni incluir secretos en el repositorio.    