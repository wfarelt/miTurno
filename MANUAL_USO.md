# Manual de Uso - miTurno (CitaPro)

Este manual es una guia practica para empezar a usar la app desde cero.

## 1) Que es esta app

miTurno es un backend SaaS multi-tenant para agenda de citas.

Conceptos clave:
- Tenant/Business: cada negocio (peluqueria/barberia) es un tenant aislado.
- Usuario autenticado con JWT.
- API multi-tenant: casi todas las llamadas requieren el header `X-Business-Slug`.
- Flujo de reserva: primero se crea un hold temporal y luego se confirma la cita con `hold_token`.

## 2) Primer arranque local

En la raiz del proyecto:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Verifica salud:

```bash
curl http://127.0.0.1:8000/health/
```

Documentacion interactiva:
- Swagger: http://127.0.0.1:8000/api/docs/
- Schema: http://127.0.0.1:8000/api/schema/

## 3) Panel admin (superadmin)

Accede con tu superusuario en:
- http://127.0.0.1:8000/admin/

Dashboard global de plataforma (solo superadmin):
- http://127.0.0.1:8000/admin/dashboard/

En admin puedes gestionar:
- Usuarios
- Negocios (Business)
- Membresias (TenantMembership)
- Servicios
- Empleados
- Citas
- Notificaciones y Outbox

## 4) Camino rapido por API (primer flujo completo)

Base URL:

```bash
BASE_URL="http://127.0.0.1:8000"
```

### Paso 1. Registrar owner + negocio

Este endpoint crea usuario + business + membresia OWNER_ADMIN automaticamente.

```bash
curl -X POST "$BASE_URL/api/v1/auth/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner1@example.com",
    "username": "owner1",
    "password": "Admin12345",
    "business_name": "Barberia Demo",
    "business_slug": "barberia-demo"
  }'
```

### Paso 2. Login JWT

```bash
curl -X POST "$BASE_URL/api/v1/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner1@example.com",
    "password": "Admin12345"
  }'
```

Guarda el `access` token en `TOKEN`.

### Paso 3. Ver perfil actual

```bash
curl "$BASE_URL/api/v1/auth/me/" \
  -H "Authorization: Bearer TOKEN"
```

### Paso 4. Ver negocio actual (tenant)

Importante: enviar `X-Business-Slug`.

```bash
curl "$BASE_URL/api/v1/business/me/" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo"
```

### Paso 5. Crear servicio

```bash
curl -X POST "$BASE_URL/api/v1/services/" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Corte clasico",
    "description": "Corte con acabado",
    "duration_minutes": 30,
    "price": "25.00",
    "is_active": true
  }'
```

Guarda el `id` del servicio (ejemplo: `SERVICE_ID=1`).

### Paso 6. Crear empleado con disponibilidad

```bash
curl -X POST "$BASE_URL/api/v1/employees/" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo" \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Ana",
    "last_name": "Barber",
    "email": "ana@barberia.com",
    "phone": "3001234567",
    "title": "Barber",
    "is_active": true,
    "availabilities": [
      {"day_of_week": 1, "start_time": "09:00:00", "end_time": "18:00:00"}
    ],
    "time_off_entries": []
  }'
```

Guarda el `id` del empleado (ejemplo: `EMPLOYEE_ID=1`).

### Paso 7. Consultar disponibilidad

```bash
curl "$BASE_URL/api/v1/appointments/availability/?date=2026-04-20&employee_id=EMPLOYEE_ID&duration=30" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo"
```

Toma un slot de respuesta (`starts_at`, `ends_at`).

### Paso 8. Crear hold temporal (5 minutos)

`ends_at - starts_at` debe coincidir con la duracion del servicio.

```bash
curl -X POST "$BASE_URL/api/v1/appointments/holds/" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo" \
  -H "Content-Type: application/json" \
  -d '{
    "employee": EMPLOYEE_ID,
    "service": SERVICE_ID,
    "starts_at": "2026-04-20T10:00:00Z",
    "ends_at": "2026-04-20T10:30:00Z"
  }'
```

Guarda el `token` del hold en `HOLD_TOKEN`.

### Paso 9. Confirmar cita usando hold_token

```bash
curl -X POST "$BASE_URL/api/v1/appointments/" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo" \
  -H "Content-Type: application/json" \
  -d '{
    "employee": EMPLOYEE_ID,
    "service": SERVICE_ID,
    "starts_at": "2026-04-20T10:00:00Z",
    "ends_at": "2026-04-20T10:30:00Z",
    "status": "CONFIRMED",
    "notes": "Primera visita",
    "hold_token": "HOLD_TOKEN"
  }'
```

Si el slot se tomo o el hold vencio, responde `409 Conflict`.

## 5) Notificaciones

### Auditoria de notificaciones (manager/owner)

```bash
curl "$BASE_URL/api/v1/notifications/?status=PENDING&channel=EMAIL" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo"
```

### Dashboard de notificaciones

```bash
curl "$BASE_URL/api/v1/notifications/dashboard/?start_at=2026-04-01&end_at=2026-04-30" \
  -H "Authorization: Bearer TOKEN" \
  -H "X-Business-Slug: barberia-demo"
```

## 6) Operacion por comandos (mantenimiento)

```bash
python manage.py cleanup_expired_holds
python manage.py schedule_appointment_notifications --lookahead-hours 48
python manage.py dispatch_due_notifications --limit 100 --max-retries 3
```

## 7) Si quieres tareas automaticas con Celery

En terminales separadas:

```bash
celery -A config worker -l info
celery -A config beat -l info
```

Config por defecto:
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/1`

## 8) Errores comunes y como resolverlos

- `403` en endpoints de negocio:
  - Falta `Authorization: Bearer ...`
  - Falta `X-Business-Slug`
  - El usuario no tiene rol en ese tenant

- `409` al crear hold/cita:
  - Slot ocupado
  - Hold vencido o token invalido
  - Rango horario no coincide con duracion del servicio

- `400` en dashboard de notificaciones:
  - `start_at` o `end_at` con formato invalido
  - Usa `YYYY-MM-DD` o datetime ISO

## 9) Recomendacion para empezar hoy

Orden sugerido para no bloquearte:
1. Crear superadmin y entrar a `/admin/` para inspeccionar modelos.
2. Ejecutar el flujo rapido API de la seccion 4.
3. Verificar que se creen notificaciones y revisar dashboard de notificaciones.
4. Activar Celery cuando ya tengas Redis disponible.
