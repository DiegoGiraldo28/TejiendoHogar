# Plan de implementación: TejiendoHogar, Fase 1

## Alcance
- Crear el proyecto Django modular con configuración `dev` y `prod`, templates del lado del servidor y PostgreSQL.
- Implementar exclusivamente usuarios y autenticación: registro Cliente, login con selector validado, logout POST, recuperación, perfil y control de acceso por rol.
- Dejar las carpetas de catálogo, pedidos, inventario y alertas sin lógica de negocio.
- Añadir pruebas pytest, workflow de CI y documentación de instalación.

## Reglas del proyecto
- `tejiendohogar_schema.sql` es la fuente de verdad para la tabla `usuario`; no ejecutar ni modificar ese SQL.
- No agregar Django Admin, API REST, frameworks CSS/JS, Node, ni dependencias ajenas al stack declarado.
- Mantener reglas de negocio en `apps/accounts/services.py`, formularios y vistas delgadas, comentarios breves en español y CSRF activo.
- No incluir secretos en el repositorio. Desarrollo lee `.env`; producción mantiene AWS como TODO sin activarlo.
- Antes de entregar, verificar configuración, pruebas y cobertura si el entorno y PostgreSQL disponibles lo permiten. No hacer commits.

## Próximas fases
Implementar catálogo, pedidos e inventario después de aprobar esta fase; las alertas PLUS quedan para su fase definida.
