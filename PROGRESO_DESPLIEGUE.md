# Progreso de corrección de despliegue

## Preparación
- Estado: a medias
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`
- Pruebas agregadas: ninguna
- Comandos ejecutados y resultado:
  - `pwd` → `C:\Users\Diego Giraldo\OneDrive\Documentos\proyectosPY\TejiendoHogar\TejiendoHogar`
  - `git remote -v` → `origin https://github.com/DiegoGiraldo28/TejiendoHogar.git` (fetch/push)
  - `git branch --show-current` → `main`
  - `git log -1 --oneline` → `0abaaad corrige incidencias de la auditoría externa`
  - `git status --short --branch` → `## main...origin/main` (Git mostró además un aviso de fsmonitor IPC)
  - `Test-Path backend/manage.py`, `.ebextensions`, `AGENTS.md` → los tres existen.
- Confirmado: el árbol versionado está limpio y `AGENTS.md` contiene «Archivos de despliegue».\n- Intento de rama `git switch -c fix/TEJ-XX-incidencias-despliegue` → falló: permiso denegado al crear `.git/refs/heads/fix/TEJ-XX-incidencias-despliegue.lock`.\n- Falta: crear la rama solicitada y ejecutar la línea base.


## D1–D7 y verificación final
- Estado: pendiente (no iniciados por bloqueo de línea base).
- Archivos tocados: ninguno.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado: no aplica.
- Falta: resolver el entorno de ejecución y retomar desde el paso 2 de preparación.

## Reintento de línea base con el entorno virtual indicado
- Estado: pendiente (bloqueado por ruta de intérprete inexistente en este checkout).
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado:
  - Desde `backend/`, se intentó el comando con `..\venv\Scripts\python.exe`; PowerShell indicó que no reconoce el comando.
  - `Test-Path ..\venv\Scripts\python.exe` desde `backend/` → `False`.
  - `Test-Path .\venv\Scripts\python.exe` desde la raíz → `False`.
  - Se comprobó también `..\..\venv\Scripts\python.exe` desde `backend/` → `False`.
- Falta: que el entorno virtual esté disponible en la ruta indicada (o indicar su ruta completa correcta). No se ejecutaron más comandos de línea base ni se inició D1–D7.

## Ruta del entorno virtual corregida
- Estado: hecho.
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comando ejecutado desde la raíz: `Test-Path ..\.venv\Scripts\python.exe` → `True`.
- Falta: ejecutar la línea base desde `backend/` con `..\..\.venv\Scripts\python.exe`.

## Línea base (primer intento con el intérprete externo correcto)
- Estado: a medias; PostgreSQL está bloqueado por el sandbox.
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados desde `backend/` con `..\..\.venv\Scripts\python.exe`:
  - `-m pytest --cov=apps --cov-report=term-missing` → 7 pasaron, 127 errores de setup, todos por `psycopg2.OperationalError: Permission denied (10013)` al conectar a `localhost:5432`.
  - `manage.py check` → sin problemas.
  - `manage.py makemigrations --check --dry-run` → `No changes detected`, pero advirtió que no pudo verificar el historial de migraciones por el mismo bloqueo a PostgreSQL.
  - `-m pycodestyle apps config` → sin salida, código 0.
- Falta: aprobación para ejecutar pruebas/comandos de Django con acceso a PostgreSQL, repetir línea base y registrar resultados concluyentes antes de comenzar D1.

## Línea base completa
- Estado: hecho.
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados desde `backend/` mediante `..\..\.venv\Scripts\python.exe` y con acceso a PostgreSQL aprobado:
  - `-m pytest --cov=apps --cov-report=term-missing` → 134 pasaron; cobertura total 96%.
  - `manage.py check` → sin problemas.
  - `manage.py makemigrations --check --dry-run` → sin cambios detectados.
  - `-m pycodestyle apps config` → 0 infracciones.
- Acceso a PostgreSQL: primer intento bloqueado por sandbox; repetición aprobada ejecutó toda la línea base correctamente.

## Preparación técnica e inspección de configuración
- Estado: hecho.
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Archivos leídos: `AGENTS.md`, `.ebextensions/01_django.config`, `backend/config/settings/prod.py`, `base.py`, `wsgi.py`, `Procfile`, `requirements.txt`, archivos en `backend/requirements/`, `backend/setup.cfg`, `.github/workflows/ci.yml`, `backend/apps/accounts/views.py`, `frontend/templates/accounts/recuperar.html`, `backend/apps/accounts/tests/test_accounts.py` y `README.md`.
- Configuración EB actual: `DJANGO_SETTINGS_MODULE=config.settings.prod`; proxy estático `/static: frontend/staticfiles`; comandos `01_migrate` (leader_only, `migrate --noinput`), `02_collectstatic` (`collectstatic --noinput`, sin `--settings` explícito pero toma `DJANGO_SETTINGS_MODULE`), `03_superusuario` (leader_only), `04_datos_demo` (leader_only).
- Plataforma/tipo de entorno: la configuración es de Elastic Beanstalk para Linux/Python (usa `.ebextensions`, `container_commands`, Procfile y el proxy `staticfiles`). No declara versión de plataforma (AL2 vs AL2023) ni tipo (instancia única vs balanceador); no hay configuración `.platform` previa.
- La vista de recuperación usa `frontend/templates/accounts/recuperar.html`; las pruebas de cuentas viven en `backend/apps/accounts/tests/test_accounts.py`.
- Falta: ejecutar D1–D7 y verificar qué puede afirmarse sobre la versión/plataforma a partir de la configuración disponible.

## D1 – HTTPS y cabeceras seguras
- Estado: hecho.
- Archivos tocados: `backend/config/settings/prod.py`, `backend/apps/accounts/tests/test_prod_settings.py`.
- Pruebas agregadas: `test_ajustes_https_segun_variable` (true/1/yes/false, cabeceras, valores seguros, origen CSRF).
- Comandos ejecutados y resultado:
  - `python -m pytest -q` con el intérprete `.venv` → 138 pasaron.
  - `python manage.py check` → sin problemas.
  - `check --deploy` con `HTTPS_ACTIVO=true` → única advertencia `security.W021` (preload no habilitado, según decisión).
  - `check --deploy` con `HTTPS_ACTIVO=false` → advertencias esperadas `W004`, `W008`, `W012`, `W016`: HSTS, redirección HTTPS y cookies seguras permanecen apagados mientras no haya certificado.
- Falta: ninguno para D1.

## D2 – Límite de subida de nginx
- Estado: a medias (configuración lista; versión de plataforma no declarada en el repositorio).
- Archivos tocados: `.platform/nginx/conf.d/tamano_subidas.conf`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna; verificación manual de 1,5 MB, 3 MB y 6 MB debe hacerse después del despliegue.
- Comandos ejecutados y resultado: creada configuración `client_max_body_size 5M;` para el path `.platform/nginx/conf.d/`.
- Plataforma/tipo: repo configura EB Linux/Python, pero no identifica AL2 o AL2023 ni instancia única/balanceador. La ruta `.platform` se aplica en las plataformas Linux compatibles; el integrante que publique debe confirmar la plataforma configurada en EB.
- Falta: comprobar con despliegue que 1,5 MB se acepta, 3 MB muestra validación Django de 2 MB y 6 MB responde 413; confirmar familia AL2/AL2023 en el entorno EB.

## Verificación de D2
- Estado: hecho (configuración comprobada; validación de tamaños y plataforma exacta siguen manuales).
- Archivos tocados: ninguno adicional.
- Pruebas agregadas: ninguna.
- Comandos ejecutados: `python -m pytest -q` → 138 pasaron; `python manage.py check` → sin problemas (con `.venv` y PostgreSQL autorizado).
- Falta: comprobaciones posteriores al despliegue listadas en el apartado D2.

## D3 – Ruta de archivos estáticos
- Estado: a medias.
- Archivos tocados: `.ebextensions/01_django.config`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados: `02_collectstatic` actual usa `DJANGO_SETTINGS_MODULE=config.settings.prod` configurado en `option_settings` y ejecuta `collectstatic --noinput`.
- Falta: cambiar el destino proxy a `/static: staticfiles` y ejecutar verificación de paso.

## D3 – Ruta de archivos estáticos
- Estado: hecho.
- Archivos tocados: `.ebextensions/01_django.config`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado: `python -m pytest -q` → 138 pasaron; `python manage.py check` → sin problemas. `02_collectstatic` usa `--noinput`; `.ebextensions` declara `DJANGO_SETTINGS_MODULE=config.settings.prod` y `manage.py` usa dev solo como `setdefault`, así que el valor EB prevalece.
- Falta: validar visualmente `/static/` tras publicación.

## D4 – Datos de demostración
- Estado: a medias.
- Archivos tocados: `.ebextensions/01_django.config`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados: ninguno para D4 todavía.
- Falta: quitar el comando de carga automática de demo, verificar pytest y check, documentar que los datos ya existentes no se eliminan.

## D4 – Datos de demostración
- Estado: hecho.
- Archivos tocados: `.ebextensions/01_django.config`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado: `python -m pytest -q` → 138 pasaron; `python manage.py check` → sin problemas. Se quitó `04_datos_demo`; `cargar_datos_demo` permanece disponible para desarrollo.
- Falta: durante la publicación confirmar que no se recargaron datos demo; las filas ya existentes en producción no se borran con este cambio.

## D5 – Aviso de SES sandbox
- Estado: a medias.
- Archivos tocados: `backend/config/settings/prod.py`, `backend/apps/accounts/views.py`, `frontend/templates/accounts/recuperar.html`, `backend/apps/accounts/tests/test_accounts.py`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: aviso visible cuando el ajuste es `True`; oculto con `False` y sin ajuste.
- Comandos ejecutados: ninguno para D5 todavía.
- Falta: ejecutar pytest y check del paso; comprobar estilo luego de D6.

## D5 – Aviso de SES sandbox
- Estado: hecho.
- Archivos tocados: `backend/config/settings/prod.py`, `backend/apps/accounts/views.py`, `frontend/templates/accounts/recuperar.html`, `backend/apps/accounts/tests/test_accounts.py`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: aviso visible/enlace `mailto:` para `True`; oculto para `False` y cuando el ajuste no existe en desarrollo.
- Comandos ejecutados y resultado: primera ejecución reveló error de limpieza de `LazySettings` en pruebas; se corrigió el aislamiento con `override_settings`. Repetición `python -m pytest -q` → 141 pasaron; `python manage.py check` → sin problemas.
- Falta: ninguno para D5.

## D6 – Estilo de `prod.py`
- Estado: a medias.
- Archivos tocados: `backend/setup.cfg`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados: ninguno para D6 todavía.
- Falta: quitar `prod.py` de la exclusión, corregir infracciones que aparezcan y verificar pycodestyle, pytest y check.

## D6 – Estilo de `prod.py`
- Estado: hecho.
- Archivos tocados: `backend/setup.cfg`, `backend/config/settings/prod.py`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado: primer pycodestyle encontró un espacio en blanco final; corregido. Repetición `python -m pycodestyle apps config` → 0 infracciones; `python -m pytest -q` → 141 pasaron; `python manage.py check` → sin problemas.
- Falta: ninguno para D6.

## D7 – Documentación de despliegue
- Estado: hecho.
- Archivos tocados: `README.md`, `REPORTE_DESPLIEGUE.md`, `PROGRESO_DESPLIEGUE.md`.
- Pruebas agregadas: ninguna.
- Comandos ejecutados y resultado: búsqueda confirmó ausentes los textos obsoletos; `python -m pytest -q` → 141 pasaron; `python manage.py check` → sin problemas.
- Falta: ninguna documentación; quedan acciones manuales tras publicación indicadas en el reporte.
## Verificación final
- Estado: hecho; D2 conserva validaciones manuales pendientes de publicación.
- Archivos tocados: `PROGRESO_DESPLIEGUE.md`, `REPORTE_DESPLIEGUE.md`.
- Pruebas agregadas: 4 funciones nuevas (una parametrizada en cuatro valores y tres pruebas SES), 7 casos nuevos en total. No se renombraron ni modificaron pruebas existentes.
- Comandos ejecutados y resultado: línea base 134 pasaron, 96% cobertura; final 141 pasaron, 96% cobertura. `manage.py check` sin problemas; `makemigrations --check --dry-run` sin cambios; `pycodestyle apps config` 0 infracciones; `git diff --check main` limpio. `check --deploy` con HTTPS activo solo `W021`; con HTTPS inactivo `W004`, `W008`, `W012`, `W016`. Búsqueda de TODO en prod.py sin resultados. `git diff --stat main` mostró 7 archivos versionados, todos dentro del alcance; los artefactos solicitados y nuevos archivos están sin seguimiento.
- Comandos de verificación final posteriores a limpieza: `manage.py check`, `makemigrations --check --dry-run`, pycodestyle y diff check pasaron.
- Falta: pruebas manuales posteriores a despliegue y confirmación de plataforma/tipo EB; no se desplegó.



