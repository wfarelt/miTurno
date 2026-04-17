# CitaPro (miTurno)

Backend SaaS multi-tenant para agendamiento de citas de peluquerias/barberias.

Estado actual: fase inicial implementada con Django + DRF + JWT + dominio multi-tenant.

## Stack

- Django 6
- Django REST Framework
- JWT con djangorestframework-simplejwt
- PostgreSQL (configurable por variables de entorno)
- Fallback SQLite para arranque local rapido

## Modulos implementados

- accounts: usuario personalizado y registro inicial
- tenants: Business (tenant), memberships y roles
- services: servicios del negocio
- staffs: empleados, disponibilidad semanal y excepciones
- appointments: citas y base de disponibilidad
- notifications: entidad base para recordatorios

## Roles implementados

- OWNER_ADMIN
- MANAGER
- EMPLOYEE
- CLIENT

## Variables de entorno

Usa `.env.example` como referencia.

Si defines `POSTGRES_DB`, la app usara PostgreSQL.
Si no, usara SQLite local.

## Instalacion local

1. Crear/activar entorno virtual
2. Instalar dependencias

```bash
pip install -r requirements.txt
```

3. Ejecutar migraciones

```bash
python manage.py migrate
```

4. Levantar servidor

```bash
python manage.py runserver
```

## Endpoints base

- Health: `GET /health/`
- OpenAPI schema: `GET /api/schema/`
- Swagger: `GET /api/docs/`

Auth:
- Register: `POST /api/v1/auth/register/`
- Login JWT: `POST /api/v1/auth/token/`
- Refresh JWT: `POST /api/v1/auth/token/refresh/`
- Current user: `GET /api/v1/auth/me/`

Tenant/Business:
- Business actual: `GET/PATCH /api/v1/business/me/`

Catalogo:
- Services CRUD: `/api/v1/services/`
- Employees CRUD: `/api/v1/employees/`

Agenda:
- Appointments CRUD: `/api/v1/appointments/`
- Create slot hold: `POST /api/v1/appointments/holds/`
- Availability basica: `GET /api/v1/appointments/availability/?date=YYYY-MM-DD&employee_id=<id>&duration=30`

## Flujo de reserva transaccional (actual)

1. Cliente solicita hold temporal (5 minutos)
2. Backend crea token de hold para el slot
3. Cliente confirma cita con `hold_token`
4. Backend valida token vigente y crea cita dentro de transaccion con lock
5. Si hay conflicto, responde `409 Conflict`

Para crear cita ahora debes enviar `hold_token` en `POST /api/v1/appointments/`.

## Resolucion de tenant

La API detecta tenant por:

1. Header `X-Business-Slug`
2. Subdominio (primer segmento del host)

## Siguiente fase recomendada

- Reserva transaccional con hold token real + expiracion
- Locks a nivel DB para anti doble-reserva dura
- Notificaciones asincronas con Celery (email/WhatsApp)
- Dashboard y reportes por negocio
