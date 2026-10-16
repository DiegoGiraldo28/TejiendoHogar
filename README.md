# TejiendoHogar

Aplicación monolítica Django con PostgreSQL y plantillas del servidor. La Fase 1 implementa usuarios y autenticación. La Fase 2 implementa gestión de productos, insumos, entradas, recetas y panel para la Emprendedora, además del catálogo público y un resumen provisional de pedido para el Cliente. El pedido no se persiste; carrito, checkout y pago corresponden a la Fase 3.

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
python -m pytest --cov=apps.accounts --cov=apps.catalog --cov=apps.inventory --cov=apps.alerts --cov=apps.orders --cov-report=term-missing --cov-fail-under=80
python manage.py check
```

En CI se usa PostgreSQL 16 efímero y Python 3.12. Las pruebas necesitan una base de pruebas accesible según las variables `DB_*`.

## Prueba de carga del equipo

Con los datos demo listos, inicia el servidor con `python backend/manage.py runserver`. En K6 o JMeter configura una solicitud `GET` a `http://127.0.0.1:8000/catalogo/`, usa 500 usuarios virtuales o hilos, aumenta la concurrencia gradualmente y registra duración, percentiles y errores. Ejecuta la medición con la base local disponible y sin depurar el servidor en producción; K6/JMeter son herramientas externas del equipo y no forman parte de las dependencias del proyecto.

## Seguridad y despliegue

No compartas `.env`, claves ni contraseñas. Producción, AWS/S3 y SES permanecen como estructura documentada sin recursos ni credenciales activos.
