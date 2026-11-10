# Reporte de corrección de despliegue

Rama: `fix/TEJ-XX-incidencias-despliegue`. No se hizo commit, push ni despliegue.

## Incidencias

| ID | Archivos | Verificación | Estado |
|---|---|---|---|
| D1 | `backend/config/settings/prod.py`, `backend/apps/accounts/tests/test_prod_settings.py` | Ajustes importados aislados con HTTPS activo/inactivo; `check --deploy` activo mostró solo `W021`; inactivo mostró `W004`, `W008`, `W012`, `W016`. | Corregida |
| D2 | `.platform/nginx/conf.d/tamano_subidas.conf`, `README.md` | Configuración `client_max_body_size 5M`; pruebas manuales de 1,5/3/6 MB documentadas, pendientes de publicación. El repositorio no declara versión AL2/AL2023 ni tipo de entorno. | Parcial; requiere confirmar plataforma y prueba manual |
| D3 | `.ebextensions/01_django.config` | Proxy estático apunta a `staticfiles`; `02_collectstatic` conserva `--noinput`; `.ebextensions` declara `DJANGO_SETTINGS_MODULE=config.settings.prod` y `manage.py` solo usa dev como `setdefault`, por lo que el valor EB prevalece. | Corregida |
| D4 | `.ebextensions/01_django.config`, `README.md` | Eliminado `04_datos_demo`; no se borran filas demo preexistentes. Confirmación posterior al despliegue pendiente. | Corregida; requiere confirmación manual |
| D5 | `backend/config/settings/prod.py`, `backend/apps/accounts/views.py`, `frontend/templates/accounts/recuperar.html`, `backend/apps/accounts/tests/test_accounts.py` | Pruebas cubren aviso visible, falso y ajuste ausente; suite completa verde. | Corregida |
| D6 | `backend/config/settings/prod.py`, `backend/setup.cfg` | `pycodestyle apps config` con 0 infracciones. | Corregida |
| D7 | `README.md` | Sección revisada y se verificó que no conserva los textos obsoletos indicados. | Corregida |

## Variables para Elastic Beanstalk

No se incluyen valores secretos. Los valores de base de datos y nombres de dominio deben reemplazarse por los reales del entorno.

| Variable | Hoy, sin HTTPS | Con certificado |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` | `config.settings.prod` |
| `SECRET_KEY` | Generar clave aleatoria larga y privada | Mantener el mismo valor |
| `ALLOWED_HOSTS` | Dominios/cname reales del sitio | Dominios/cname HTTPS; revisar si el health check usa IP de instancia |
| `DB_NAME` | Nombre real de la base RDS | Mantener |
| `DB_USER` | Usuario de aplicación RDS | Mantener |
| `DB_PASSWORD` | Contraseña privada RDS | Mantener |
| `DB_HOST` | Endpoint DNS de RDS | Mantener |
| `DB_PORT` | `5432` | `5432` |
| `AWS_STORAGE_BUCKET_NAME` | Nombre real del bucket privado | Mantener |
| `AWS_S3_REGION_NAME` | Región real del bucket, por ejemplo `us-east-1` | Mantener |
| `EMAIL_HOST` | `email-smtp.us-east-1.amazonaws.com` o host de la región SES | Mantener |
| `EMAIL_PORT` | `587` | `587` |
| `EMAIL_HOST_USER` | Credencial SMTP SES privada | Mantener |
| `EMAIL_HOST_PASSWORD` | Credencial SMTP SES privada | Mantener |
| `DEFAULT_FROM_EMAIL` | Remitente verificado en SES | Mantener |
| `HTTPS_ACTIVO` | `false` | `true` |
| `CSRF_TRUSTED_ORIGINS` | Vacía si el sitio es HTTP | Lista de orígenes `https://` separados por comas |
| `SES_SANDBOX` | `true` si SES continúa en sandbox; de lo contrario `false` | Según estado de SES; no depende de HTTPS |

## Publicación y comprobación manual

1. Configurar las variables de entorno de la tabla. Hoy, mientras no exista certificado, mantener `HTTPS_ACTIVO=false` y `CSRF_TRUSTED_ORIGINS` vacía.
2. Confirmar en la consola de Elastic Beanstalk que la plataforma es Amazon Linux 2 o Amazon Linux 2023 y revisar si el entorno es instancia única o usa balanceador. Publicar el artefacto siguiendo el procedimiento del equipo.
3. Confirmar la aplicación de `accounts 0002`, `catalog 0002`, `catalog 0003` e `inventory 0002`. Revisar `unaccent` con `SELECT extname FROM pg_extension;`. Desde PostgreSQL 13 la extensión es *trusted*: el usuario de aplicación puede crearla si tiene permiso `CREATE` en la base; si no, hacerlo con el usuario maestro de RDS.
4. Abrir el catálogo y comprobar que `/static/` carga correctamente estilos e imágenes servidos desde `staticfiles`.
5. Subir archivos de 1,5 MB (aceptado), 3 MB (mensaje de validación Django de máximo 2 MB) y 6 MB (respuesta 413 de nginx).
6. Abrir `/recuperar/` con `SES_SANDBOX=true` y comprobar el aviso con enlace `mailto:diegoh.giraldoc@uqvirtual.edu.co`; cambiar a `false` y comprobar que desaparece.
7. Confirmar que no se recargaron datos demo. Eliminar el comando de carga automática no borra datos demo que ya existieran.

Cuando se habilite HTTPS: instalar un certificado, configurar el listener 443, activar `HTTPS_ACTIVO=true` y configurar `CSRF_TRUSTED_ORIGINS`. El health check HTTP puede recibir 301; aceptar 200–399 o usar health check HTTPS. Revisar que `ALLOWED_HOSTS` acepte el host del health check, que podría ser la IP de la instancia. Después de verificar el sitio completo, aumentar HSTS de 3600 a 31536000 segundos. `SECURE_HSTS_PRELOAD` permanece apagado.

## Riesgos y tareas manuales pendientes

- No se puede determinar desde los archivos del repositorio la versión exacta de Amazon Linux ni el tipo de entorno EB. La configuración `.platform` se preparó para las plataformas Linux EB compatibles; el publicador debe confirmar AL2/AL2023.
- Al activar HTTPS, un health check por HTTP puede recibir redirección 301. `ALLOWED_HOSTS` podría rechazar el health check si este envía la IP de la instancia. No se modificó código para estos riesgos.
- No se ejecutó despliegue ni se probaron cargas HTTP reales; tamaños 1,5/3/6 MB, estilos en vivo, correo SES y datos demo se deben verificar después de publicar.
- Las cuentas SES en sandbox solo pueden enviar a destinatarios verificados; `SES_SANDBOX=true` muestra el aviso correspondiente.

## Pruebas agregadas o modificadas

No se renombraron ni modificaron pruebas existentes. Se agregaron:

- `test_ajustes_https_segun_variable` (casos `true`, `1`, `yes`, `false`): cabeceras, cookies, proxy, HSTS y separación de `CSRF_TRUSTED_ORIGINS`.
- `test_aviso_ses_sandbox_visible_con_enlace_mailto`.
- `test_aviso_ses_sandbox_oculto_con_ajuste_falso`.
- `test_aviso_ses_sandbox_oculto_si_ajuste_no_existe`.

## Verificación ejecutada

- Línea base y verificación final con Python 3.12.7 del entorno `.venv` externo al repositorio.
- Línea base: 134 pruebas pasaron; cobertura total 96%; `check`, `makemigrations --check --dry-run` y pycodestyle correctos.
- Final: 141 pruebas pasaron; cobertura total 96%; `check` sin problemas; `makemigrations --check --dry-run` informó que no hay cambios; pycodestyle con 0 infracciones.
- `check --deploy`: con HTTPS activo mostró solo `security.W021`; sin HTTPS mostró `W004`, `W008`, `W012`, `W016`, esperados hasta que exista certificado y todo el sitio use HTTPS.
- `prod.py` no contiene `TODO`.

## Mensaje de commit sugerido

`TEJ-XX: corrige configuración de despliegue según auditoría`

