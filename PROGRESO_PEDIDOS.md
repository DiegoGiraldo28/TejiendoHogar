# Progreso — Proceso 3: Gestión de Pedidos (no versionar)

Plan aprobado: `~/.claude/plans/pasted-content-id-ec6c-tejiendohogar-pr-stateful-cookie.md`.
Rama: `feature/TEJ-XX-proceso-pedidos` (creada desde `main` @ `ae172c8`). Sin commits.
Intérprete: `..\..\.venv\Scripts\python.exe` desde `backend/`.

## Paso 0 — Línea base (hecho)
- `pytest --cov=apps`: **141 passed** (114 s), cobertura total 96 %.
- Cobertura por app: accounts 99 %, alerts 100 %, catalog 95 %, common 100 %, inventory 93 %, legal 100 %, orders 100 %.
- `manage.py check`: sin problemas. `makemigrations --check --dry-run`: No changes detected. `pycodestyle apps config`: 0.

## Etapa A
| Punto | Estado | Archivos | Pruebas | Comandos / resultado | Falta |
|---|---|---|---|---|---|
| A1 | hecho | `orders/models.py`, `orders/migrations/0001_initial.py` | `test_modelos.py` | makemigrations OK; migrate OK | — |
| A2 | hecho | `inventory/models.py`, `inventory/migrations/0003_movimientoinsumo_pedido.py` | `test_movimiento_exige_pedido_segun_su_tipo` | migrate OK | — |
| A3 | hecho | `inventory/services.py` (`descontar_insumos`, `devolver_insumos`) | `test_servicios.py` | — | — |
| A4 | hecho | `orders/carrito.py`, `orders/services.py`, `common/constants.py` (DIAS_ALISTAMIENTO) | `test_servicios.py` | — | — |
| A5 | hecho | `orders/pagos.py`, `config/settings/base.py` (PASARELA_PAGO) | `test_pasarela_configurada_es_la_simulada` | — | — |
| A6 | hecho | `orders/migrations/0002_triggers.py` | `test_trigger_*` | migrate OK | — |
| A7 | hecho | `orders/tests/ayudantes.py`, `test_modelos.py`, `test_servicios.py`, `test_concurrencia.py` | 62 nuevas | `pytest` 203 passed; `check` OK; `makemigrations --check` sin cambios; `pycodestyle` 0 | — |

Precisiones del usuario aplicadas: (1) RechazoPedido sin pedido persiste fuera del bloque revertido en `crear_pedido` (prueba `test_crear_pedido_registra_rechazo_por_*_aunque_se_revierta`); (2) `preparar_pedido_desde_bolsa` verifica dueña y estado Pendiente (3 pruebas `test_preparar_pedido_*`); (3) `PedidoYaConfirmado` para el doble envío (vista en Etapa B).
SQL de sqlmigrate: en `REPORTE_PEDIDOS.md` §3. **Etapa A terminada: esperando revisión del usuario.**

## Etapa B — pendiente (esperar revisión de A)
- Pendiente en B: la vista de pago debe capturar `PedidoYaConfirmado` → redirigir al seguimiento con `messages.info("Tu pedido ya fue confirmado")`.
- `orders/views.py`, `forms.py`, `urls.py`, la plantilla `en_proceso.html` y `tests/test_orders.py` siguen con la página provisional (se retiran en B6).
## Etapa C — pendiente
