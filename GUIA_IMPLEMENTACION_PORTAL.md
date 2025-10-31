# 🚀 GUÍA DE IMPLEMENTACIÓN - Portal de Usuarios con Sistema de Login

## 📋 Resumen

Has solicitado mejorar el portal de facturación con las siguientes características:

1. ✅ **Crear tabla `facturas`** en PostgreSQL
2. ✅ **Sistema de usuarios** con login (email + receiver_id)
3. ✅ **Creación automática de usuarios** cuando solicitan factura
4. ✅ **Portal de clientes** donde ven sus facturas, PDFs, XMLs
5. ✅ **Workflow n8n actualizado** para crear usuario y responder con credenciales

---

## 🗄️ PASO 1: Crear las Tablas en PostgreSQL

### Ejecutar el schema SQL:

```bash
cd /home/dml/portal_facturacion

# Conectar a PostgreSQL y ejecutar
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre -f database_schema.sql
```

**O manualmente:**

```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre
```

Luego dentro de psql:

```sql
\i database_schema.sql
```

### Tablas creadas:

1. **usuarios_portal** - Usuarios del portal (login con email + receiver_id)
2. **facturas** - Todas las facturas generadas
3. **sesiones_portal** - Control de sesiones
4. **historial_accesos** - Log de accesos
5. **notificaciones** - Notificaciones para usuarios

### Verificar que se crearon:

```sql
\dt
-- Debe mostrar: usuarios_portal, facturas, sesiones_portal, historial_accesos, notificaciones

SELECT * FROM usuarios_portal;
SELECT * FROM facturas;
```

---

## 🔧 PASO 2: Actualizar app.py

### Opción A: Agregar receiver_id al payload

Necesitas modificar `app.py` para incluir el `receiver_id` que viene de la tabla `orden_ml`.

**Modificar función `buscar_pedido()` (línea 58):**

```python
def buscar_pedido(search_id):
    """
    Busca un pedido por order_id, pack_id o payment_id
    ACTUALIZADO: Ahora incluye receiver_id y shipment_id
    """
    conn = get_db_connection()
    if not conn:
        return None

    cursor = None
    try:
        cursor = conn.cursor()

        # Incluir receiver_id y shipment_id en la consulta
        query = """
            SELECT order_id, paid_amount, buyer_nickname, currency_id,
                   receiver_id, shipment_id
            FROM public.orden_ml
            WHERE order_id = %s OR pack_id = %s
        """
        cursor.execute(query, (search_id, search_id))
        row = cursor.fetchone()

        if not row:
            query = """
                SELECT order_id, paid_amount, buyer_nickname, currency_id,
                       receiver_id, shipment_id
                FROM public.orden_ml
                WHERE payments_0_id = %s
            """
            cursor.execute(query, (search_id,))
            row = cursor.fetchone()

        if row:
            return {
                'order_id': row[0],
                'paid_amount': float(row[1]) if row[1] else 0,
                'buyer_nickname': row[2],
                'currency_id': row[3],
                'receiver_id': row[4],  # ← NUEVO
                'shipment_id': row[5]   # ← NUEVO
            }
        return None

    except psycopg2.Error as e:
        app.logger.error(f"Error buscando pedido: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
```

**Modificar función `procesar_factura()` (línea 404):**

Agregar al payload:

```python
    # Payload para n8n
    payload = {
        # Datos del pedido
        'order_id': order['order_id'],
        'paid_amount': order['paid_amount'],
        'currency_id': order.get('currency_id', 'MXN'),

        # ← NUEVO: Datos del comprador
        'receiver_id': order.get('receiver_id'),
        'shipment_id': order.get('shipment_id'),
        'nombre': order.get('buyer_nickname', f"Cliente ML - {order['order_id']}"),

        # Datos de facturación
        'email': email,
        'phone': phone,
        'cfdi_usage': cfdi_usage,
        'payment_method': payment_method,
        'monto_pagado': monto_pagado_float,

        # PDF de CSF (en base64)
        'csf_pdf': {
            'filename': filename,
            'content': pdf_content,
            'mime_type': 'application/pdf'
        },

        # Metadata
        'timestamp': datetime.now().isoformat(),
        'source': 'portal_flask'
    }
```

### Opción B: Integrar módulo de portal de usuarios

Puedes agregar el archivo `portal_usuarios.py` que ya está en el directorio:

**Al final de app.py, ANTES del `if __name__ == '__main__'`:**

```python
# ============================================================================
# PORTAL DE USUARIOS - SISTEMA DE LOGIN
# ============================================================================

from portal_usuarios import (
    login_required,
    portal_login,
    portal_login_post,
    portal_logout,
    portal_dashboard,
    portal_factura_detalle,
    portal_notificaciones,
    # ... importar todas las rutas necesarias
)

# O simplemente incluir todo el código de portal_usuarios.py aquí
```

**O ejecutar:**

```bash
cd /home/dml/portal_facturacion
cat portal_usuarios.py >> app.py
```

---

## 🔄 PASO 3: Workflow n8n YA ACTUALIZADO

El workflow **DWubtvcV5fyjkWGw** ya está actualizado con:

✅ **15 nodos** (antes tenía 14)
✅ **Nuevo nodo:** "Crear/Actualizar Usuario Portal"
✅ **Email actualizado** con credenciales de acceso
✅ **Respuesta del webhook** incluye datos de acceso al portal

### Nodos agregados/modificados:

1. **Crear/Actualizar Usuario Portal** (después de Decodificar PDF)
   - Query SQL con `INSERT ... ON CONFLICT ... DO UPDATE`
   - Crea usuario o actualiza si ya existe
   - Usa receiver_id como contraseña

2. **Email mejorado** con:
   - Diseño HTML profesional
   - Credenciales de acceso al portal
   - URL del portal
   - Email + receiver_id para login

3. **Respuesta Success** ahora incluye:
   ```json
   {
     "success": true,
     "invoice_id": "12345",
     "order_id": "ABC123",
     "portal_access": {
       "url": "http://tu-dominio.com/portal",
       "email": "cliente@example.com",
       "password": "receiver_id_del_cliente",
       "mensaje": "Usa tu email y tu número de cliente ML..."
     }
   }
   ```

---

## ⚙️ PASO 4: Configurar Variables de Entorno

### En n8n, configurar variable de entorno:

1. Abre n8n: https://aut.automateai.com.mx
2. Settings → Environment Variables
3. Agregar:

```
PORTAL_URL = http://tu-dominio.com/portal/login
```

O directamente en el servidor donde corre n8n:

```bash
export PORTAL_URL="http://tu-dominio.com/portal/login"
```

---

## 🎨 PASO 5: Crear Templates HTML

Crear en `/home/dml/portal_facturacion/templates/portal/`:

```bash
mkdir -p /home/dml/portal_facturacion/templates/portal
cd /home/dml/portal_facturacion/templates/portal
```

Necesitas crear:

1. **login.html** - Página de login
2. **dashboard.html** - Dashboard principal con lista de facturas
3. **factura_detalle.html** - Ver una factura específica
4. **notificaciones.html** - Ver notificaciones
5. **perfil.html** - Ver/editar perfil

### Ejemplo login.html:

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portal de Facturas - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container">
        <div class="row justify-content-center mt-5">
            <div class="col-md-5">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white text-center">
                        <h4>Portal de Facturas DML Medica</h4>
                    </div>
                    <div class="card-body">
                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ 'danger' if category == 'error' else category }}">
                                        {{ message }}
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST" action="{{ url_for('portal_login_post') }}">
                            <div class="mb-3">
                                <label for="email" class="form-label">Email</label>
                                <input type="email" class="form-control" id="email" name="email" required>
                            </div>
                            <div class="mb-3">
                                <label for="receiver_id" class="form-label">Número de Cliente ML</label>
                                <input type="text" class="form-control" id="receiver_id" name="receiver_id" required>
                                <small class="text-muted">Tu receiver_id de Mercado Libre</small>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Iniciar Sesión</button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
```

---

## 🧪 PASO 6: Probar el Sistema

### 1. Ejecutar SQL para crear tablas:

```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre -f database_schema.sql
```

### 2. Actualizar app.py con receiver_id

Ver PASO 2 arriba.

### 3. Reiniciar Flask:

```bash
cd /home/dml/portal_facturacion
python3 app.py
```

### 4. Probar flujo completo:

1. Ir a http://localhost:5000
2. Buscar un pedido
3. Llenar formulario de facturación
4. **Enviar** → n8n procesa y crea usuario
5. **Revisar email** con credenciales
6. **Ir a** http://localhost:5000/portal/login
7. **Login** con email + receiver_id
8. **Ver dashboard** con facturas

---

## 📊 Flujo Completo del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    PORTAL FLASK (app.py)                        │
│                                                                 │
│  1. Cliente busca pedido (order_id, pack_id, payment_id)      │
│  2. Se obtiene receiver_id de orden_ml                         │
│  3. Cliente llena formulario (email, teléfono, CSF PDF)        │
│  4. Flask envía todo a n8n via webhook                         │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                  WORKFLOW N8N (15 nodos)                        │
│                                                                 │
│  1. Webhook recibe datos                                        │
│  2. Valida si ya existe factura (Postgres)                     │
│     ├─ SI → Responde error                                     │
│     └─ NO → Continúa                                           │
│  3. Decodifica PDF de CSF                                      │
│  4. **CREA/ACTUALIZA USUARIO en usuarios_portal** ← NUEVO     │
│  5. Busca cliente en Odoo                                      │
│  6. Crea cliente si no existe                                  │
│  7. Crea factura en Odoo                                       │
│  8. **GUARDA factura en tabla facturas con usuario_id** ← NUEVO│
│  9. Envía email con:                                           │
│     - PDF CSF adjunto                                          │
│     - **Credenciales de acceso al portal** ← NUEVO            │
│  10. Responde success con:                                     │
│     - invoice_id                                               │
│     - **portal_access (url, email, password)** ← NUEVO        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│              PORTAL DE USUARIOS (portal_usuarios.py)            │
│                                                                 │
│  1. Cliente va a /portal/login                                 │
│  2. Login con email + receiver_id                              │
│  3. Dashboard muestra:                                         │
│     - Lista de facturas                                        │
│     - Estatus de pago                                          │
│     - Observaciones de contabilidad                            │
│     - Links para descargar PDF y XML                           │
│  4. Cliente puede:                                             │
│     - Ver detalle de facturas                                  │
│     - Descargar PDF/XML                                        │
│     - Ver notificaciones                                       │
│     - Actualizar perfil (RFC, razón social, etc.)             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Sistema de Autenticación

### Cómo funciona:

1. **Primera factura:**
   - Cliente solicita factura
   - n8n crea usuario en `usuarios_portal`
   - Password = receiver_id del comprador en Mercado Libre
   - Email enviado con credenciales

2. **Login:**
   - Cliente ingresa email + receiver_id
   - Sistema valida en tabla `usuarios_portal`
   - Si coincide, crea sesión

3. **Dashboard:**
   - Muestra facturas filtradas por `usuario_id`
   - Solo ve sus propias facturas

### Seguridad:

- ✅ receiver_id es único por comprador
- ✅ Historial de accesos registrado
- ✅ Bloqueo temporal después de intentos fallidos
- ✅ Sesiones con timeout
- ⚠️ **Para producción:** Usar HTTPS obligatorio

---

## 📁 Archivos Creados

```
/home/dml/portal_facturacion/
├── app.py                          # Archivo principal (MODIFICAR)
├── portal_usuarios.py              # ✅ NUEVO - Sistema de login
├── database_schema.sql             # ✅ NUEVO - Schema SQL
├── GUIA_IMPLEMENTACION_PORTAL.md   # ✅ NUEVO - Esta guía
└── templates/
    └── portal/                     # ✅ CREAR
        ├── login.html
        ├── dashboard.html
        ├── factura_detalle.html
        ├── notificaciones.html
        └── perfil.html
```

---

## ✅ Checklist de Implementación

- [ ] **1. Ejecutar database_schema.sql en PostgreSQL**
- [ ] **2. Verificar que se crearon las 5 tablas**
- [ ] **3. Modificar app.py para incluir receiver_id**
- [ ] **4. Agregar portal_usuarios.py a app.py**
- [ ] **5. Crear templates HTML en templates/portal/**
- [ ] **6. Configurar PORTAL_URL en n8n**
- [ ] **7. Verificar que workflow n8n está activo (ya está)**
- [ ] **8. Probar flujo completo de solicitud de factura**
- [ ] **9. Probar login al portal**
- [ ] **10. Verificar que usuario puede ver sus facturas**

---

## 🆘 Troubleshooting

### Error: "tabla facturas no existe"

```bash
# Verificar conexión
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre

# Dentro de psql
\dt

# Si no aparece, ejecutar:
\i /home/dml/portal_facturacion/database_schema.sql
```

### Error: "receiver_id no está en payload"

Modificar `buscar_pedido()` en app.py para incluir receiver_id (ver PASO 2).

### Error: "No se puede importar portal_usuarios"

```bash
# Verificar que está en el directorio
ls -lh /home/dml/portal_facturacion/portal_usuarios.py

# Agregar al inicio de app.py:
# from portal_usuarios import *
```

### Workflow n8n no crea usuario

Verificar credenciales de PostgreSQL en n8n y que el nodo "Crear/Actualizar Usuario Portal" tenga la consulta correcta.

---

## 📞 Próximos Pasos

1. Ejecutar `database_schema.sql`
2. Modificar `app.py` (agregar receiver_id)
3. Crear templates HTML
4. Probar flujo completo

¿Necesitas ayuda con algún paso específico?
