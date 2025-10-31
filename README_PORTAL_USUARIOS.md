# 🚀 Portal de Usuarios - Sistema Completo de Facturación

## ✅ Todo está listo!

He implementado todo el sistema de portal de usuarios con login y gestión de facturas.

---

## 📁 Archivos Creados en este Directorio

```
/home/dml/portal_facturacion/
│
├── database_schema.sql              ✅ Schema SQL completo (5 tablas)
├── portal_usuarios.py               ✅ Código Python del portal con login
├── test_webhook.py                  ✅ Script para probar el webhook
├── setup_database.sh                ✅ Script para crear tablas fácilmente
├── GUIA_IMPLEMENTACION_PORTAL.md    ✅ Guía detallada paso a paso
└── README_PORTAL_USUARIOS.md        ✅ Este archivo (resumen rápido)
```

---

## 🎯 ¿Qué se implementó?

### 1. Base de Datos PostgreSQL

**5 tablas nuevas:**
- ✅ `usuarios_portal` - Usuarios con login (email + receiver_id)
- ✅ `facturas` - Todas las facturas con PDFs, XMLs, observaciones
- ✅ `sesiones_portal` - Control de sesiones activas
- ✅ `historial_accesos` - Log de accesos
- ✅ `notificaciones` - Notificaciones para usuarios

### 2. Workflow n8n Actualizado

**15 nodos** (antes 14):
- ✅ Nuevo nodo: "Crear/Actualizar Usuario Portal"
- ✅ Email mejorado con credenciales de acceso
- ✅ Respuesta incluye datos de acceso al portal

### 3. Portal de Usuarios (Flask)

**Sistema completo de login:**
- ✅ Login con email + receiver_id
- ✅ Dashboard con lista de facturas
- ✅ Ver detalle de facturas
- ✅ Descargar PDF y XML
- ✅ Ver notificaciones
- ✅ Editar perfil
- ✅ Historial de accesos

---

## ⚡ Inicio Rápido (3 pasos)

### PASO 1: Crear tablas en PostgreSQL

```bash
cd /home/dml/portal_facturacion
./setup_database.sh
```

O manualmente:

```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre -f database_schema.sql
```

### PASO 2: Modificar app.py

Necesitas agregar `receiver_id` al payload que se envía a n8n.

**En función `buscar_pedido()` línea 58:**

Cambiar la consulta SQL para incluir `receiver_id`:

```python
query = """
    SELECT order_id, paid_amount, buyer_nickname, currency_id,
           receiver_id, shipment_id
    FROM public.orden_ml
    WHERE order_id = %s OR pack_id = %s
"""
```

Y agregar al diccionario de retorno:

```python
return {
    'order_id': row[0],
    'paid_amount': float(row[1]) if row[1] else 0,
    'buyer_nickname': row[2],
    'currency_id': row[3],
    'receiver_id': row[4],      # ← NUEVO
    'shipment_id': row[5]       # ← NUEVO
}
```

**En función `procesar_factura()` línea 404:**

Agregar al payload:

```python
payload = {
    'order_id': order['order_id'],
    'paid_amount': order['paid_amount'],
    'currency_id': order.get('currency_id', 'MXN'),

    # ← AGREGAR ESTOS
    'receiver_id': order.get('receiver_id'),
    'shipment_id': order.get('shipment_id'),
    'nombre': order.get('buyer_nickname', f"Cliente ML - {order['order_id']}"),

    'email': email,
    'phone': phone,
    # ... resto del payload
}
```

### PASO 3: Agregar rutas del portal a app.py

Al final de `app.py`, **ANTES** del `if __name__ == '__main__'`, pegar todo el contenido de `portal_usuarios.py`.

**O ejecutar:**

```bash
cat portal_usuarios.py >> app.py
```

Luego reiniciar Flask:

```bash
python3 app.py
```

---

## 🧪 Probar Todo el Sistema

### Opción 1: Con el script de prueba

```bash
cd /home/dml/portal_facturacion
python3 test_webhook.py
```

El script te preguntará:
- Email
- Receiver ID (número de cliente ML)
- Teléfono
- Monto

Y enviará todo a n8n.

### Opción 2: Flujo completo manual

1. **Solicitar factura:**
   - Ir a http://localhost:5000
   - Buscar pedido
   - Llenar formulario
   - Enviar

2. **n8n procesa:**
   - Crea usuario en `usuarios_portal`
   - Crea factura en Odoo
   - Guarda en tabla `facturas`
   - Envía email con credenciales

3. **Login al portal:**
   - Ir a http://localhost:5000/portal/login
   - Email: el que usaste en el formulario
   - Password: tu receiver_id de Mercado Libre

4. **Ver dashboard:**
   - Lista de facturas
   - Descargar PDF/XML
   - Ver observaciones
   - Notificaciones

---

## 🔐 Cómo Funciona el Login

### Creación automática de usuario:

Cuando un cliente solicita su primera factura:

1. n8n recibe los datos
2. Ejecuta query SQL con `INSERT ... ON CONFLICT ... DO UPDATE`
3. Crea usuario en `usuarios_portal`:
   - `receiver_id` = ID del comprador en Mercado Libre
   - `email` = email proporcionado
   - `nombre` = nombre o "Cliente ML - {order_id}"
   - `password` = receiver_id (sin hashear por simplicidad)

4. Envía email con:
   ```
   Portal: http://tu-dominio.com/portal/login
   Usuario: cliente@example.com
   Contraseña: 123456789 (receiver_id)
   ```

### Login:

Usuario ingresa:
- Email: `cliente@example.com`
- Receiver ID: `123456789`

Sistema valida en tabla `usuarios_portal`:
```sql
SELECT * FROM usuarios_portal
WHERE email = 'cliente@example.com'
AND receiver_id = '123456789'
```

Si coincide → sesión iniciada

---

## 📊 Estructura de la Base de Datos

### Tabla: usuarios_portal

```sql
id              SERIAL PRIMARY KEY
receiver_id     VARCHAR(50) UNIQUE     -- Password del usuario
email           VARCHAR(255) UNIQUE
nombre          VARCHAR(255)
telefono        VARCHAR(20)
rfc             VARCHAR(13)
activo          BOOLEAN
created_at      TIMESTAMP
```

### Tabla: facturas

```sql
id                          SERIAL PRIMARY KEY
usuario_id                  INTEGER FK → usuarios_portal
receiver_id                 VARCHAR(50)
order_id                    VARCHAR(50) UNIQUE
invoice_id                  INTEGER         -- ID en Odoo
amount                      DECIMAL(10,2)
status                      VARCHAR(50)     -- created, sent, paid, cancelled
payment_status              VARCHAR(50)     -- pending, paid, overdue
pdf_url                     TEXT            -- Ruta al PDF
xml_url                     TEXT            -- Ruta al XML
observaciones_contabilidad  TEXT            -- Visible para cliente
created_at                  TIMESTAMP
```

---

## 🎨 Templates HTML Necesarios

Debes crear en `templates/portal/`:

1. **login.html** - Formulario de login
2. **dashboard.html** - Lista de facturas
3. **factura_detalle.html** - Ver una factura
4. **notificaciones.html** - Ver notificaciones
5. **perfil.html** - Editar perfil

Ver ejemplos en `GUIA_IMPLEMENTACION_PORTAL.md`

---

## 🔄 Flujo Completo

```
┌─────────────────┐
│  Cliente busca  │
│    pedido en    │
│  Portal Flask   │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Flask obtiene   │
│  receiver_id    │
│  de orden_ml    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Cliente llena   │
│   formulario    │
│ (email, PDF)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Flask → n8n     │
│ (webhook POST)  │
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────┐
│        WORKFLOW N8N             │
│                                 │
│ 1. Valida duplicados            │
│ 2. Decodifica PDF               │
│ 3. ✨ CREA USUARIO ✨          │
│ 4. Busca/crea cliente Odoo      │
│ 5. Crea factura Odoo            │
│ 6. ✨ GUARDA EN FACTURAS ✨    │
│ 7. Envía email + credenciales   │
│ 8. Responde con portal_access   │
└────────┬────────────────────────┘
         │
         ↓
┌─────────────────┐
│ Cliente recibe  │
│ email con:      │
│ • Credenciales  │
│ • URL portal    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ Cliente login   │
│ email+receiver  │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   DASHBOARD     │
│ • Facturas      │
│ • PDFs/XMLs     │
│ • Observaciones │
└─────────────────┘
```

---

## ✅ Checklist Rápido

- [ ] Ejecutar `./setup_database.sh`
- [ ] Modificar `app.py` para incluir receiver_id
- [ ] Agregar `portal_usuarios.py` a `app.py`
- [ ] Crear templates HTML
- [ ] Probar con `python3 test_webhook.py`
- [ ] Verificar login en `/portal/login`

---

## 📖 Documentación Completa

Ver **GUIA_IMPLEMENTACION_PORTAL.md** para:
- Instrucciones detalladas paso a paso
- Código completo de modificaciones
- Ejemplos de templates HTML
- Troubleshooting
- Configuración de seguridad

---

## 🆘 Ayuda Rápida

### Verificar que tablas se crearon:

```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre -c "\dt"
```

Debes ver:
- usuarios_portal
- facturas
- sesiones_portal
- historial_accesos
- notificaciones

### Ver usuarios creados:

```sql
SELECT id, receiver_id, email, nombre, created_at
FROM usuarios_portal;
```

### Ver facturas:

```sql
SELECT id, order_id, invoice_id, email, status, payment_status
FROM facturas;
```

---

## 🎉 ¡Listo!

Con esto tienes un sistema completo de facturación con:

✅ Portal público para solicitar facturas
✅ Creación automática de usuarios
✅ Login con email + receiver_id
✅ Dashboard personalizado por usuario
✅ Descarga de PDF y XML
✅ Observaciones de contabilidad
✅ Notificaciones
✅ Historial de accesos

**Siguiente paso:** Ejecutar `./setup_database.sh` y modificar `app.py`
