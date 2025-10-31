# ✅ CAMBIOS REALIZADOS EN APP.PY - Sistema de Login Funcional

## 📝 Resumen de Cambios

He modificado `app.py` para implementar un sistema completo de login con dashboard para que los usuarios puedan ver sus facturas.

---

## 🔧 Modificaciones en app.py

### 1. **Importaciones agregadas** (líneas 14-19)

```python
from psycopg2.extras import RealDictCursor  # Para obtener resultados como diccionarios
from functools import wraps  # Para el decorador login_required
from flask import send_file  # Para descargar PDFs y XMLs
```

### 2. **buscar_pedido() actualizada** (líneas 73-100)

**Agregado:**
- `receiver_id` - ID del comprador en Mercado Libre (para login)
- `shipment_id` - ID del envío

**Resultado:**
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

### 3. **procesar_factura() actualizada** (líneas 408-437)

**Agregado al payload para n8n:**
```python
# Datos del comprador (para crear usuario en portal)
'receiver_id': order.get('receiver_id'),
'shipment_id': order.get('shipment_id'),
'nombre': order.get('buyer_nickname', f"Cliente ML - {order['order_id']}"),
```

### 4. **Sistema de Portal agregado** (líneas 631-1036)

**Funciones auxiliares:**
- `login_required()` - Decorador para proteger rutas
- `registrar_acceso()` - Registra logins en historial_accesos
- `actualizar_ultimo_acceso()` - Actualiza timestamp de último acceso

**Rutas de autenticación:**
- `GET /portal/login` - Muestra formulario de login
- `POST /portal/login` - Procesa el login
- `GET /portal/logout` - Cierra sesión

**Rutas del dashboard:**
- `GET /portal/dashboard` - Dashboard con lista de facturas
- `GET /portal/factura/<id>` - Ver detalle de una factura
- `GET /portal/factura/<id>/pdf` - Descargar PDF
- `GET /portal/factura/<id>/xml` - Descargar XML

---

## 🎨 Templates HTML Creados

### 1. `/templates/portal/login.html`
- Formulario de login moderno
- Campos: email + receiver_id
- Link para solicitar factura si no tiene cuenta

### 2. `/templates/portal/dashboard.html`
- Sidebar con navegación
- Cards con estadísticas (total facturas, monto, pendientes, pagadas)
- Tabla con todas las facturas del usuario
- Botones para ver detalle, descargar PDF/XML
- Botón para solicitar nueva factura

### 3. `/templates/portal/factura_detalle.html`
- Detalle completo de la factura
- Información de pago
- Observaciones de contabilidad
- Botones de descarga de PDF y XML

---

## 🔐 Cómo Funciona el Sistema de Login

### **Flujo Completo:**

```
1. CLIENTE SOLICITA FACTURA (Primera vez)
   ↓
   - Va a http://localhost:5000
   - Busca pedido (order_id)
   - Flask obtiene receiver_id de orden_ml
   - Llena formulario y envía

2. N8N PROCESA Y CREA USUARIO
   ↓
   - Recibe payload con receiver_id
   - Ejecuta: INSERT INTO usuarios_portal (receiver_id, email, nombre)
   - Envía email con credenciales:
     * Email: cliente@example.com
     * Password: receiver_id (ej: 123456789)

3. CLIENTE INICIA SESIÓN
   ↓
   - Va a http://localhost:5000/portal/login
   - Ingresa email + receiver_id
   - Sistema valida en tabla usuarios_portal

4. DASHBOARD
   ↓
   - Ve todas sus facturas
   - Puede descargar PDF/XML
   - Puede solicitar nuevas facturas
```

---

## 🧪 Cómo Probar

### **PASO 1: Crear las tablas en PostgreSQL**

```bash
cd /home/dml/portal_facturacion
./setup_database.sh
```

O manualmente:
```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre -f database_schema.sql
```

### **PASO 2: Verificar que receiver_id existe en orden_ml**

```bash
psql -h 192.168.80.8 -p 30432 -U dml -d mercadoLibre
```

```sql
SELECT order_id, receiver_id, buyer_nickname
FROM orden_ml
LIMIT 5;
```

Debe retornar datos con `receiver_id` poblado.

### **PASO 3: Reiniciar Flask**

```bash
cd /home/dml/portal_facturacion
python3 app.py
```

### **PASO 4: Solicitar una factura**

1. Ir a http://localhost:5000
2. Buscar un pedido existente (usar un order_id real de orden_ml)
3. Llenar formulario de facturación
4. Enviar

**n8n automáticamente:**
- Creará usuario en `usuarios_portal`
- Enviará email con credenciales
- Guardará factura en tabla `facturas`

### **PASO 5: Iniciar sesión**

1. Ir a http://localhost:5000/portal/login
2. Ingresar:
   - Email: el que usaste en el formulario
   - Receiver ID: obténlo de la consulta SQL arriba
3. Verás el dashboard con tus facturas

---

## 📊 Estructura de Rutas

```
PÚBLICO (sin login):
  GET  /                      → Buscar pedido
  POST /buscar-pedido         → Procesar búsqueda
  GET  /facturar/<order_id>   → Formulario de facturación
  POST /procesar-factura      → Enviar a n8n
  GET  /exito/<order_id>      → Confirmación

PORTAL (requiere login):
  GET  /portal/login          → Formulario de login
  POST /portal/login          → Procesar login
  GET  /portal/logout         → Cerrar sesión
  GET  /portal/dashboard      → Dashboard principal
  GET  /portal/factura/<id>   → Detalle de factura
  GET  /portal/factura/<id>/pdf → Descargar PDF
  GET  /portal/factura/<id>/xml → Descargar XML
```

---

## 🔑 Seguridad Implementada

1. **Login con credenciales:**
   - Email + receiver_id (único por comprador en ML)

2. **Protección de rutas:**
   - Decorador `@login_required` en todas las rutas del portal

3. **Validación de pertenencia:**
   - Los usuarios solo ven SUS facturas (`WHERE usuario_id = session['usuario_id']`)

4. **Historial de accesos:**
   - Todos los logins se registran en `historial_accesos`

5. **Bloqueo temporal:**
   - Sistema soporta bloqueo después de intentos fallidos

---

## 📋 Checklist de Validación

- [ ] Tablas creadas en PostgreSQL
- [ ] receiver_id existe en orden_ml
- [ ] Flask corriendo sin errores
- [ ] Puedo solicitar una factura
- [ ] n8n crea usuario automáticamente
- [ ] Puedo hacer login en /portal/login
- [ ] Veo el dashboard con facturas
- [ ] Puedo ver detalle de factura
- [ ] Puedo descargar PDF/XML (si existen)
- [ ] Puedo solicitar nueva factura desde dashboard

---

## ⚠️ Notas Importantes

1. **receiver_id debe existir:**
   - Si tu tabla `orden_ml` no tiene `receiver_id`, la consulta fallará
   - Verifica primero con: `SELECT * FROM orden_ml LIMIT 1;`

2. **PDFs y XMLs:**
   - Los links de descarga funcionan si los paths existen en `facturas.pdf_url` y `facturas.xml_url`
   - Si no existen, se muestra mensaje "no disponible"

3. **Credenciales en email:**
   - El email lo envía n8n (workflow ya está configurado)
   - El password es el `receiver_id` sin encriptar (simple pero funcional)

4. **Sesiones Flask:**
   - Se usa `session` de Flask
   - SECRET_KEY debe estar configurado en Config (ya está)

---

## 🚀 Próximos Pasos

1. **Crear las tablas:**
   ```bash
   ./setup_database.sh
   ```

2. **Verificar receiver_id en BD:**
   ```sql
   SELECT order_id, receiver_id FROM orden_ml LIMIT 1;
   ```

3. **Probar el flujo completo:**
   - Solicitar factura → Login → Dashboard

4. **Opcional - Mejorar:**
   - Agregar cambio de contraseña
   - Agregar recuperación de contraseña
   - Agregar notificaciones en tiempo real
   - Agregar perfil de usuario

---

## ❓ Preguntas Frecuentes

**P: ¿Dónde se crea el usuario?**
R: En n8n, el nodo "Crear/Actualizar Usuario Portal" ejecuta el INSERT en `usuarios_portal`.

**P: ¿Qué pasa si el usuario ya existe?**
R: Se usa `ON CONFLICT DO UPDATE`, así que se actualiza con los datos más recientes.

**P: ¿Cómo sabe n8n el receiver_id?**
R: Flask lo obtiene de `orden_ml` y lo envía en el payload al webhook.

**P: ¿Puedo cambiar la contraseña?**
R: Actualmente no, pero se puede agregar una ruta para eso.

**P: ¿Los PDFs se descargan automáticamente?**
R: No, el usuario hace clic en el botón "Descargar PDF" en el dashboard.

---

**Estado:** ✅ COMPLETO Y LISTO PARA PROBAR
**Última actualización:** 2025-10-30
