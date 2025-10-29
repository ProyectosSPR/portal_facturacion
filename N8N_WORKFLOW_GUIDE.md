# Guía de Workflow n8n para Portal de Facturación

## Arquitectura del Sistema

```
Usuario → Flask (UI) → n8n Webhook → [Validaciones + Odoo + Email] → Respuesta a Flask
                                ↓
                          Callbacks opcionales
```

## 1. Webhook de Entrada (Recibe datos de Flask)

### URL del Webhook
Configure en Flask: `N8N_WEBHOOK_URL=https://your-n8n.com/webhook/facturacion`

### Datos que Recibe (POST JSON)

```json
{
  "order_id": "1234567890",
  "paid_amount": 1500.00,
  "currency_id": "MXN",

  "email": "cliente@example.com",
  "phone": "5512345678",
  "cfdi_usage": "G01",
  "payment_method": "03",
  "monto_pagado": 1500.00,

  "csf_pdf": {
    "filename": "1234567890_csf.pdf",
    "content": "JVBERi0xLjQKJeLjz9MKM...",  // Base64
    "mime_type": "application/pdf"
  },

  "timestamp": "2024-01-15T10:30:00",
  "source": "portal_flask"
}
```

## 2. Flujo del Workflow n8n

### Paso 1: Webhook Node (Recibir Datos)
- **Node**: Webhook
- **Method**: POST
- **Path**: `/facturacion`
- **Response Mode**: Wait For Webhook

### Paso 2: Validar Elegibilidad (Reglas A y B)

#### 2.1 Consultar Shipment (Postgres)
```sql
-- Node: Postgres - Query Shipment
SELECT id, logistic_type, status
FROM public.shipment
WHERE id = (
  SELECT shipping_id
  FROM public.orden_ml
  WHERE order_id = '{{ $json.order_id }}'
)
```

#### 2.2 Evaluar Regla A o B (Function Node)
```javascript
// Node: Function - Determinar Regla

const shipment = $input.first().json;
const logisticType = shipment.logistic_type?.toLowerCase();

// REGLA A: Full o Agencia (elegible inmediatamente)
if (logisticType === 'fulfillment' || logisticType === 'cross_docking') {
  return {
    json: {
      ...items[0].json,
      business_rule: 'A',
      eligible: true,
      reason: 'Mercado Envíos Full/Agencia',
      needs_payment_check: false
    }
  };
}

// REGLA B: Requiere verificar pago liberado
return {
  json: {
    ...items[0].json,
    business_rule: 'B',
    needs_payment_check: true
  }
};
```

#### 2.3 Si Regla B: Verificar Pago Liberado (Postgres)
```sql
-- Node: Postgres - Verificar Pago (solo si needs_payment_check = true)
SELECT
  pm.id,
  pm.status,
  pm.money_release_status,
  pm.money_release_date
FROM pagos_mercadopago pm
LEFT JOIN orden_ml om ON pm.id = om.payments_0_id
WHERE
  om.order_id = '{{ $json.order_id }}'
  AND (pm.status = 'approved' OR pm.status = 'authorized')
  AND (
    (pm.collector_id IS NULL AND pm.money_release_status = 'pending')
    OR (pm.money_release_status = 'released')
  )
  AND pm.odoo_reccord IS DISTINCT FROM true
  AND NOT (
    pm.collector_id IS NOT NULL AND
    pm.transaction_details_net_received_amount = 0 AND
    pm.status_detail = 'accredited'
  )
LIMIT 1;
```

#### 2.4 Verificar Elegibilidad Final (IF Node)
```javascript
// Si no hay pago liberado (Regla B), detener con error
if ($json.needs_payment_check && !$json.payment_data) {
  return {
    json: {
      success: false,
      message: 'El pago aún no ha sido liberado por Mercado Libre. Intenta más tarde.'
    }
  };
}
```

### Paso 3: Verificar si Ya Fue Facturado (Postgres)
```sql
-- Node: Postgres - Check Facturado
SELECT record_odoo, id_record_odoo
FROM public.orden_ml
WHERE order_id = '{{ $json.order_id }}'
  AND record_odoo = true;
```

**IF Node**: Si ya está facturado, retornar error:
```json
{
  "success": false,
  "message": "Este pedido ya ha sido facturado previamente."
}
```

### Paso 4: Guardar PDF en Odoo o Servidor (Opcional)
```javascript
// Node: Function - Decodificar PDF

const pdfBase64 = $json.csf_pdf.content;
const pdfBuffer = Buffer.from(pdfBase64, 'base64');

return {
  json: {
    ...$json,
    pdf_binary: pdfBuffer
  },
  binary: {
    csf_pdf: {
      data: pdfBuffer,
      mimeType: 'application/pdf',
      fileName: $json.csf_pdf.filename
    }
  }
};
```

### Paso 5: Buscar o Crear Partner en Odoo

#### 5.1 Buscar Partner (Odoo Node)
- **Resource**: Contact
- **Operation**: Get Many
- **Filter**: `email = '{{ $json.email }}'`

#### 5.2 Si No Existe, Crear Partner (Odoo Node)
- **Resource**: Contact
- **Operation**: Create
- **Fields**:
  - `name`: Nombre del comprador (o del RFC si extraes del CSF)
  - `email`: `{{ $json.email }}`
  - `phone`: `{{ $json.phone }}`
  - `customer_rank`: 1

### Paso 6: Crear Factura en Odoo (account.move)

#### 6.1 Odoo Node - Create Invoice
- **Resource**: Invoice
- **Operation**: Create
- **Fields**:
  - `partner_id`: `{{ $json.partner_id }}` (del paso anterior)
  - `move_type`: `out_invoice`
  - `state`: `draft`
  - `invoice_date`: `{{ $now.format('YYYY-MM-DD') }}`
  - `l10n_mx_edi_usage`: `{{ $json.cfdi_usage }}`
  - `l10n_mx_edi_payment_method_id`: `{{ $json.payment_method }}`
  - `ref`: `Pedido ML: {{ $json.order_id }}`

#### 6.2 Agregar Línea de Factura (invoice_line_ids)
```javascript
// Usando Custom Fields o Code Node
{
  "invoice_line_ids": [
    [0, 0, {
      "name": `Producto Mercado Libre - Pedido ${$json.order_id}`,
      "quantity": 1,
      "price_unit": $json.monto_pagado,
      "product_id": YOUR_PRODUCT_ID,  // ID del producto genérico en Odoo
      "account_id": YOUR_ACCOUNT_ID   // Cuenta contable
    }]
  ]
}
```

#### 6.3 Lógica Especial por Regla

**Si Regla A (Full/Agencia)**: Agregar etiqueta y asignar usuario
```javascript
// Function Node - Etiqueta Full
if ($json.business_rule === 'A') {
  return {
    json: {
      ...$json,
      x_etiqueta_facturacion: 'Pendiente Timbrado (Full)',
      user_id: YOUR_ODOO_USER_ID  // Usuario responsable
    }
  };
}
```

**Si Regla B (Externo)**: Marcar como pagada (opcional)
```javascript
// Registrar pago automático si es necesario
// Usar Odoo Node - Register Payment
```

### Paso 7: Actualizar record_odoo en Postgres
```sql
-- Node: Postgres - Update Order
UPDATE public.orden_ml
SET record_odoo = true,
    id_record_odoo = '{{ $json.invoice_id }}'
WHERE order_id = '{{ $json.order_id }}';
```

### Paso 8: Obtener PDF de la Factura (Odoo)
```javascript
// Node: HTTP Request - Obtener PDF
// Method: POST
// URL: {{ $env.ODOO_URL }}/web/content/
// Body:
{
  "model": "account.move",
  "id": {{ $json.invoice_id }},
  "field": "invoice_pdf_report_id",
  "download": true
}
```

### Paso 9: Enviar Email al Cliente

#### 9.1 Email Node (o SMTP Node)
- **To**: `{{ $json.email }}`
- **Subject**: `Tu Prefactura - Pedido {{ $json.order_id }}`
- **Body** (HTML):
```html
<h2>¡Hola!</h2>
<p>Tu prefactura ha sido generada exitosamente.</p>
<p><strong>Pedido:</strong> {{ $json.order_id }}</p>
<p><strong>Monto:</strong> ${{ $json.monto_pagado }} {{ $json.currency_id }}</p>
<p>Adjuntamos el PDF de tu factura en borrador.</p>
<p>Saludos,<br>Equipo de Facturación</p>
```
- **Attachments**: PDF de la factura

### Paso 10: Responder a Flask (Webhook Response)

#### Caso Éxito:
```json
{
  "success": true,
  "message": "¡Factura creada exitosamente! Se ha enviado a tu correo.",
  "invoice_id": "{{ $json.invoice_id }}",
  "order_id": "{{ $json.order_id }}"
}
```

#### Caso Error:
```json
{
  "success": false,
  "message": "Error específico aquí (pago no liberado, ya facturado, etc.)"
}
```

### Paso 11: Callbacks Opcionales a Flask

Si quieres notificar estados después de responder al webhook:

```javascript
// Node: HTTP Request - Callback (opcional)
// Method: POST
// URL: https://your-flask-app.com/webhook/factura-procesada
// Body:
{
  "order_id": "{{ $json.order_id }}",
  "status": "success",
  "invoice_id": "{{ $json.invoice_id }}",
  "message": "Factura creada y enviada por email"
}
```

## 3. Manejo de Errores

### Error Handling Node
Agregar un nodo de error al final del workflow:

```javascript
// Node: Error Handler
const error = $input.first().json;

// Log del error
console.error('Error en facturación:', error);

// Callback a Flask
return {
  json: {
    order_id: $json.order_id,
    error_type: 'processing_error',
    error_message: error.message || 'Error desconocido',
    timestamp: new Date().toISOString()
  }
};
```

**HTTP Request** a `/webhook/error-facturacion`

## 4. Estructura Visual del Workflow

```
┌─────────────┐
│  Webhook    │ Recibe datos de Flask
└──────┬──────┘
       │
       v
┌─────────────┐
│  Postgres   │ Consultar shipment
│  Shipment   │
└──────┬──────┘
       │
       v
┌─────────────┐
│  Function   │ Determinar Regla A o B
│  Regla      │
└──────┬──────┘
       │
   ┌───┴────────┐
   │            │
   v (Regla B)  v (Regla A)
┌──────────┐    │
│ Postgres │    │
│ Payment  │    │
└────┬─────┘    │
     │          │
     └────┬─────┘
          │
          v
     ┌────────┐
     │   IF   │ ¿Elegible?
     └────┬───┘
          │
     ┌────┴────┐
     │ No      │ Sí
     v         v
  [Error] ┌─────────┐
          │Postgres │ ¿Ya facturado?
          └────┬────┘
               │
          ┌────┴────┐
          │ Sí      │ No
          v         v
       [Error]  ┌────────┐
                │ Odoo   │ Buscar/Crear Partner
                └────┬───┘
                     │
                     v
                ┌────────┐
                │ Odoo   │ Crear Factura
                └────┬───┘
                     │
                     v
                ┌────────┐
                │Postgres│ Actualizar record_odoo
                └────┬───┘
                     │
                     v
                ┌────────┐
                │ Email  │ Enviar factura
                └────┬───┘
                     │
                     v
                ┌────────┐
                │Response│ Responder a Flask
                └────────┘
```

## 5. Variables de Entorno en n8n

Configure estas variables en n8n:

```
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=nombre_db
POSTGRES_USER=dml
POSTGRES_PASSWORD=***

ODOO_URL=https://your-odoo.com
ODOO_DB=nombre_db_odoo
ODOO_USERNAME=admin@example.com
ODOO_PASSWORD=***

ODOO_PRODUCT_ID=123  # ID del producto genérico para facturas ML
ODOO_ACCOUNT_ID=456  # Cuenta contable de ingresos
ODOO_USER_FULL_ID=7  # Usuario responsable de facturas Full

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=noreply@yourcompany.com
EMAIL_PASSWORD=***
```

## 6. Testing del Workflow

### Datos de Prueba (POST al webhook):
```json
{
  "order_id": "1234567890",
  "paid_amount": 100.00,
  "currency_id": "MXN",
  "email": "test@example.com",
  "phone": "5512345678",
  "cfdi_usage": "G01",
  "payment_method": "03",
  "monto_pagado": 100.00,
  "csf_pdf": {
    "filename": "test.pdf",
    "content": "JVBERi0xLjQKJeLjz9MK...",
    "mime_type": "application/pdf"
  },
  "timestamp": "2024-01-15T10:00:00",
  "source": "test"
}
```

## 7. Monitoreo y Logs

Agregar nodos de logging en puntos clave:

```javascript
// Node: Function - Log Progress
console.log(`[${$json.order_id}] Paso completado: ${$json.step}`);
console.log('Data:', JSON.stringify($json, null, 2));

return { json: $json };
```

## 8. Optimizaciones

1. **Cache de Partners**: Implementar cache en n8n para no buscar siempre en Odoo
2. **Queue**: Si hay muchas solicitudes, usar Queue node para procesar en lotes
3. **Retry Logic**: Configurar retry automático en nodos de Odoo/Postgres
4. **Webhooks Asincrónicos**: Responder rápido a Flask y procesar en background

---

**Nota**: Este workflow es el corazón del sistema. Flask solo valida y envía datos, n8n hace toda la lógica de negocio.
