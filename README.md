# TejiendoHogar

Backend Django de TejiendoHogar. Esta fase implementa únicamente registro, acceso, recuperación y perfil de usuario.

## Requisitos

- Python 3.10 o posterior (desarrollo del proyecto: Python 3.12).
- PostgreSQL 16 instalado localmente y una base vacía llamada `tejiendohogar_dev`.
- No se requiere Node, contenedores ni Django Admin.

## Instalación en Windows PowerShell

Desde la carpeta raíz del repositorio:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend/requirements/dev.txt
Copy-Item .env.example .env
```

Edita `.env` con los datos de tu base PostgreSQL local. `SECRET_KEY` debe ser una clave aleatoria local y no se debe subir al repositorio. En macOS/Linux usa `python3 -m venv venv` y `source venv/bin/activate`.

En pgAdmin 4 registra el servidor con host `localhost`, puerto `5432`, usuario y contraseña locales; crea o selecciona la base `tejiendohogar_dev` en UTF8. Las tablas de la aplicación se crean con migraciones; **no ejecutes `tejiendohogar_schema.sql`**.

```powershell
python backend/manage.py makemigrations accounts
python backend/manage.py migrate
python backend/manage.py createsuperuser
python backend/manage.py runserver
```

Visita http://127.0.0.1:8000/. El comando `createsuperuser` crea una cuenta Emprendedora. El correo de restablecimiento de contraseña aparece en la consola de desarrollo.

## Pruebas

Con el entorno virtual activado y una conexión PostgreSQL válida en `.env`:

```powershell
cd backend
pytest --cov=apps.accounts --cov-report=term-missing
```

El pipeline requiere una cobertura mínima del 80% y prepara PostgreSQL 16 automáticamente.

## Fase actual y pendientes

- Implementado: Cliente, Emprendedora y Operaria (sin panel); registro, login, logout POST, recuperación de contraseña, perfil y permisos por rol.
- Pendiente para siguientes fases: catálogo, pedidos, inventario y asistente PLUS.
- Producción: S3, SES, RDS, Elastic Beanstalk y CloudWatch están indicados como TODO; no se activan ni requieren credenciales.
