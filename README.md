# CitaPro (miTurno)

Backend SaaS multi-tenant para agendamiento de citas de peluquerias/barberias.

Guia paso a paso de uso: ver `MANUAL_USO.md`.

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

## Reglas de permisos en citas (actual)

- CLIENT: solo puede cancelar sus propias citas (`status=CANCELLED`)
- EMPLOYEE: puede editar campos no criticos (ej. notas/estado), no puede mover horario ni borrar
- MANAGER / OWNER_ADMIN: control completo sobre citas del negocio

## Mantenimiento de holds expirados

Comando para limpiar holds vencidos:

```bash
python manage.py cleanup_expired_holds
```

Modo simulacion:

```bash
python manage.py cleanup_expired_holds --dry-run
```

Filtrar por negocio:

```bash
python manage.py cleanup_expired_holds --business-slug demo
```

## Notificaciones asincronas (email + adapter WhatsApp)

El sistema agenda y despacha notificaciones con modelo `Notification`.

Eventos soportados:

- `BOOKING_CREATED`
- `APPOINTMENT_CONFIRMED`
- `REMINDER_24H`
- `REMINDER_1H`

Comandos operativos:

```bash
python manage.py schedule_appointment_notifications --lookahead-hours 48
python manage.py dispatch_due_notifications --limit 100 --max-retries 3
```

Notas:

- Email usa backend de Django (por defecto `console.EmailBackend` en local)
- WhatsApp integrado via Meta Cloud API (configurado por variables de entorno)
- Entrega robusta con patron outbox (`NotificationOutbox`) y reintentos con backoff

Auditoria por API:

- `GET /api/v1/notifications/` (solo MANAGER / OWNER_ADMIN)
- Filtros: `status`, `channel`, `event_type`
- Dashboard de metricas: `GET /api/v1/notifications/dashboard/`
	- Filtros opcionales: `start_at`, `end_at` (ISO datetime o `YYYY-MM-DD`)

Webhook WhatsApp (Meta):

- Verificacion: `GET /api/v1/notifications/webhooks/whatsapp/`
	- Query params: `hub.mode`, `hub.verify_token`, `hub.challenge`
- Eventos: `POST /api/v1/notifications/webhooks/whatsapp/`
	- Reconciliacion por `provider_message_id` en outbox
	- Estados soportados: `sent`, `delivered`, `read`, `failed`, `undelivered`

## Celery Beat (siguiente paso aplicado)

Tareas periodicas configuradas:

- `notifications.tasks.schedule_appointment_notifications_task` cada 15 minutos
- `notifications.tasks.dispatch_due_notifications_task` cada 1 minuto
- `appointments.tasks.cleanup_expired_holds_task` cada 10 minutos

Ejecucion local (terminales separadas):

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Broker/backend por defecto (configurable):

- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`

## Resolucion de tenant

La API detecta tenant por:

1. Header `X-Business-Slug`
2. Subdominio (primer segmento del host)

## Siguiente fase recomendada

- Dashboard admin con metricas de entrega por canal/evento (aplicado)
- Politicas de reintento por tipo de error (4xx vs 5xx) (aplicado)
- Circuit breaker por proveedor externo (degradacion controlada) (aplicado)


## Configuracion adicional de resiliencia

- `WHATSAPP_CIRCUIT_BREAKER_ENABLED` (default `True`)
- `WHATSAPP_CIRCUIT_FAILURE_THRESHOLD` (default `5`)
- `WHATSAPP_CIRCUIT_RECOVERY_SECONDS` (default `120`)
