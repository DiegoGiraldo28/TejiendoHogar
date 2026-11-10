# TejiendoHogar

Aplicación monolítica Django con PostgreSQL y plantillas del servidor. La Fase 1 implementa usuarios y autenticación. La Fase 2 implementa gestión de productos, insumos, entradas, recetas y panel para la Emprendedora, además del catálogo público y un resumen provisional de pedido para el Cliente. También contiene páginas informativas de términos, privacidad y cookies. El pedido no se persiste; carrito, checkout y pago corresponden a la Fase 3.

## Requisitos

- Python 3.10 o posterior (equipo de desarrollo: Python 3.12).
- PostgreSQL 16 local y una base vacía llamada `tejiendohogar_dev`.
- Git. No se requiere Node, npm, contenedores ni Django Admin.

## Instalación en Windows PowerShell

Desde la raíz del repositorio:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/dev.txt
Copy-Item .env.example .env
```

Completa `.env` con la conexión local a PostgreSQL. Mantén `.env` fuera de Git. En macOS/Linux crea el entorno con `python3 -m venv venv` y actívalo con `source venv/bin/activate`.

En pgAdmin 4 registra el servidor usando `localhost:5432`, las credenciales de tu instalación y la base `tejiendohogar_dev`. Si la base aún no existe, créala desde pgAdmin. No ejecutes `tejiendohogar_schema.sql`; Django administra el esquema con migraciones.

## Migraciones y datos de muestra

```powershell
python backend/manage.py makemigrations
python backend/manage.py migrate
python backend/manage.py cargar_datos_demo
python backend/manage.py createsuperuser
python backend/manage.py runserver
```

El comando de datos demo es idempotente y crea seis insumos, ocho productos, recetas e imágenes PNG mínimas sin dependencias de imágenes. Abre `http://127.0.0.1:8000/`.

## Probar y revisar cobertura

Entra a `backend/` y ejecuta las pruebas y la revisión de configuración desde allí:

```powershell
python -m pytest --cov=apps.accounts --cov=apps.catalog --cov=apps.inventory --cov=apps.alerts --cov=apps.orders --cov=apps.legal --cov-report=term-missing --cov-fail-under=80
python manage.py check
```

En CI se usa PostgreSQL 16 efímero y Python 3.12. Las pruebas necesitan una base de pruebas accesible según las variables `DB_*`.

## Prueba de carga del equipo

Con los datos demo listos, inicia el servidor con `python backend/manage.py runserver`. En K6 o JMeter configura una solicitud `GET` a `http://127.0.0.1:8000/catalogo/`, usa 500 usuarios virtuales o hilos, aumenta la concurrencia gradualmente y registra duración, percentiles y errores. Ejecuta la medición con la base local disponible y sin depurar el servidor en producción; K6/JMeter son herramientas externas del equipo y no forman parte de las dependencias del proyecto.

## Seguridad y despliegue

No compartas `.env`, claves ni contraseñas. Configura las variables en el entorno de Elastic Beanstalk; no las escribas en archivos versionados.

### Variables de entorno

| Nombre | Requisito | Ejemplo | Descripción |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Obligatoria | `config.settings.prod` | Módulo de configuración para el proceso web y los comandos EB. |
| `SECRET_KEY` | Obligatoria | `cambia-por-una-clave-aleatoria-larga` | Clave secreta de Django; conserva el mismo valor entre instancias y despliegues. |
| `ALLOWED_HOSTS` | Obligatoria | `tienda.example.com,www.tienda.example.com` | Nombres de host aceptados, separados por comas y sin esquema. |
| `DB_NAME` | Obligatoria | `tejiendohogar` | Base PostgreSQL de producción. |
| `DB_USER` | Obligatoria | `tejiendohogar_app` | Usuario PostgreSQL de la aplicación. |
| `DB_PASSWORD` | Obligatoria | `valor-secreto` | Contraseña del usuario PostgreSQL. |
| `DB_HOST` | Obligatoria | `mi-instancia.xxxxxx.us-east-1.rds.amazonaws.com` | Host de RDS. |
| `DB_PORT` | Opcional | `5432` | Puerto PostgreSQL; si se omite, usa `5432`. |
| `AWS_STORAGE_BUCKET_NAME` | Obligatoria | `tejiendohogar-media` | Bucket S3 privado para imágenes subidas. El rol de IAM de la instancia aporta credenciales. |
| `AWS_S3_REGION_NAME` | Opcional | `us-east-1` | Región del bucket; si se omite, usa `us-east-1`. |
| `EMAIL_HOST` | Opcional | `email-smtp.us-east-1.amazonaws.com` | Host SMTP de Amazon SES. |
| `EMAIL_PORT` | Opcional | `587` | Puerto SMTP; si se omite, usa `587`. |
| `EMAIL_HOST_USER` | Obligatoria para enviar correo | `usuario-smtp-ses` | Usuario SMTP de SES. |
| `EMAIL_HOST_PASSWORD` | Obligatoria para enviar correo | `contraseña-smtp-secreta` | Contraseña SMTP de SES. |
| `DEFAULT_FROM_EMAIL` | Opcional | `TejiendoHogar <avisos@example.com>` | Remitente verificado en SES; reemplaza el valor de desarrollo. |
| `HTTPS_ACTIVO` | Opcional | `false` hoy; `true` con certificado | Activa redirección HTTPS, cookies seguras, proxy HTTPS y HSTS inicial de una hora. Acepta `true`, `1` o `yes`, sin distinguir mayúsculas; por defecto `false`. |
| `CSRF_TRUSTED_ORIGINS` | Opcional | `https://tienda.example.com,https://www.example.com` | Orígenes separados por comas, cada uno con esquema. Por defecto, lista vacía. |
| `SES_SANDBOX` | Opcional | `false` (o `true` mientras la cuenta siga en sandbox) | Muestra el aviso de limitación de destinatarios verificados en la página de recuperación. Acepta `true`, `1` o `yes`; por defecto `false`. |

### Configuración del servidor

Elastic Beanstalk sirve estáticos desde `staticfiles`, la ruta de `STATIC_ROOT` alimentada por `collectstatic`. El límite de nginx está en `.platform/nginx/conf.d/tamano_subidas.conf` y acepta solicitudes de hasta 5 MB; Django conserva su validación y mensaje en español para imágenes mayores de 2 MB. El comando `cargar_datos_demo` no se ejecuta en producción. Los datos demo que ya existan en la base no se eliminan con este cambio.

En el próximo despliegue se aplican las migraciones `accounts 0002` (tabla `intento_acceso`), `catalog 0002`, `catalog 0003` (extensión PostgreSQL `unaccent`) e `inventory 0002`. Desde PostgreSQL 13, `unaccent` es una extensión *trusted*: normalmente basta con que el usuario de la aplicación tenga permiso `CREATE` sobre la base. Si no lo tiene, créala con el usuario maestro de RDS. Comprueba su instalación con:

```sql
SELECT extname FROM pg_extension;
```

### Activación futura de HTTPS

1. Instala un certificado válido y configura el listener 443 del balanceador hacia la aplicación.
2. Define `HTTPS_ACTIVO=true` y `CSRF_TRUSTED_ORIGINS` con los orígenes `https://` del sitio.
3. Revisa el health check del balanceador: al activar HTTPS, su solicitud HTTP puede recibir un 301; acepta los códigos 200–399 o configura el health check por HTTPS. Confirma también que `ALLOWED_HOSTS` admite el host enviado por el health check, que puede ser la IP de la instancia.
4. Después de comprobar que todo el sitio funciona por HTTPS, aumenta HSTS de 3600 a 31536000 segundos mediante un cambio revisado. `SECURE_HSTS_PRELOAD` permanece desactivado.

### Verificación manual después de publicar

1. Configura las variables de entorno anteriores y publica el artefacto en Elastic Beanstalk.
2. Confirma la aplicación de las cuatro migraciones indicadas y verifica que `unaccent` aparece en `pg_extension`.
3. Abre el catálogo y comprueba que `/static/` carga estilos e imágenes estáticas.
4. Sube una imagen de 1,5 MB (debe aceptarse), una de 3 MB (Django debe mostrar su mensaje de máximo 2 MB) y una de 6 MB (nginx debe responder 413).
5. Abre `/recuperar/` con `SES_SANDBOX=true` y confirma el aviso y enlace de contacto; con `false` debe ocultarse.
6. Confirma que el comando demo no se ejecutó. Los datos demo preexistentes permanecen en la base.
