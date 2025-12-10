# Configuración del Webhook de Descarga de Facturas en n8n

## Descripción General

Este documento explica cómo configurar el webhook de n8n para manejar las descargas de archivos PDF y XML de facturas desde el portal.

## URL del Webhook

Por defecto, la URL configurada es:
```
https://aut.automateai.com.mx/webhook/download-factura
```

Puedes cambiarla en el archivo `.env` o `config.py`:
```bash
N8N_DOWNLOAD_WEBHOOK_URL=https://tu-dominio.com/webhook/download-factura
```

## Payload que Recibe el Webhook

Cuando un usuario hace clic en "Descargar PDF" o "Descargar XML", Flask envía el siguiente JSON:

```json
{
  "invoice_id": 12345,
  "invoice_name": "INV/2024/00123",
  "order_id": "7890123456",
  "tipo_archivo": "pdf"
}
```

### Campos:
- **invoice_id**: ID numérico de la factura en Odoo
- **invoice_name**: Nombre/número de la factura (ej: INV/2024/00123)
- **order_id**: ID del pedido de Mercado Libre
- **tipo_archivo**: Puede ser `"pdf"` o `"xml"`

## Respuesta Esperada del Webhook

El webhook debe responder con:
- **Status Code**: 200 (OK)
- **Body**: El contenido binario del archivo (PDF o XML)
- **Headers**:
  - `Content-Type: application/pdf` (para PDF)
  - `Content-Type: application/xml` (para XML)

## Ejemplo de Workflow en n8n

### 1. Nodo Webhook (Trigger)
- **Webhook Method**: POST
- **Path**: `/download-factura`
- **Response Mode**: Respond to Webhook

### 2. Nodo Switch (Decidir tipo de archivo)
```javascript
// Mode: Rules
// Condiciones:
{{ $json.body.tipo_archivo === 'pdf' }} → Ruta PDF
{{ $json.body.tipo_archivo === 'xml' }} → Ruta XML
```

### 3. Nodo Odoo (Obtener Factura)
- **Resource**: Invoice
- **Operation**: Get
- **Invoice ID**: `{{ $json.body.invoice_id }}`

### 4. Nodo HTTP Request (Descargar PDF desde Odoo)
**Para PDF:**
```
URL: https://tu-odoo.com/web/content/ir.attachment/{{ $json.attachment_pdf_id }}/datas
Method: GET
Authentication: Basic Auth
Response Format: File
```

**Para XML:**
```
URL: https://tu-odoo.com/web/content/ir.attachment/{{ $json.attachment_xml_id }}/datas
Method: GET
Authentication: Basic Auth
Response Format: File
```

### 5. Nodo Respond to Webhook
- **Response Data**: Binary Data
- **Binary Property**: data (el archivo descargado)
- **Response Headers**:
  - `Content-Type`: `application/pdf` o `application/xml`
  - `Content-Disposition`: `attachment; filename="factura_{{ $json.body.order_id }}.pdf"`

## Configuración Alternativa: Archivos en Sistema de Archivos

Si los archivos PDF/XML están guardados en el sistema de archivos de n8n:

### Nodo Read Binary File
```javascript
File Path: /ruta/facturas/{{ $json.body.order_id }}_{{ $json.body.tipo_archivo }}.{{ $json.body.tipo_archivo }}
```

## Manejo de Errores

El webhook debe manejar estos casos:

1. **Factura no encontrada en Odoo**
   - Status: 404
   - Body: `{ "error": "Factura no encontrada" }`

2. **Archivo no disponible**
   - Status: 404
   - Body: `{ "error": "Archivo no disponible" }`

3. **Error al conectar con Odoo**
   - Status: 500
   - Body: `{ "error": "Error al obtener archivo" }`

## Testing

Puedes probar el webhook usando curl:

```bash
curl -X POST https://aut.automateai.com.mx/webhook/download-factura \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_id": 12345,
    "invoice_name": "INV/2024/00123",
    "order_id": "7890123456",
    "tipo_archivo": "pdf"
  }' \
  --output factura.pdf
```

## Logs

Flask registra automáticamente:
- ✅ Solicitudes de descarga exitosas
- ❌ Errores de conexión con n8n
- ⚠️ Timeouts (después de 30 segundos)

Puedes ver los logs en: `portal_facturacion.log`

## Ejemplo Completo de Workflow n8n (JSON)

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "download-factura",
        "responseMode": "responseNode",
        "httpMethod": "POST"
      }
    },
    {
      "name": "Switch por Tipo",
      "type": "n8n-nodes-base.switch",
      "parameters": {
        "rules": {
          "rules": [
            {
              "operation": "equal",
              "value1": "={{ $json.body.tipo_archivo }}",
              "value2": "pdf"
            },
            {
              "operation": "equal",
              "value1": "={{ $json.body.tipo_archivo }}",
              "value2": "xml"
            }
          ]
        }
      }
    },
    {
      "name": "Odoo - Get Invoice",
      "type": "n8n-nodes-base.odoo",
      "parameters": {
        "resource": "invoice",
        "operation": "get",
        "invoiceId": "={{ $json.body.invoice_id }}"
      }
    },
    {
      "name": "Download PDF from Odoo",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://tu-odoo.com/web/content/ir.attachment/={{ $json.attachment_ids[0] }}/datas",
        "responseFormat": "file"
      }
    },
    {
      "name": "Respond to Webhook",
      "type": "n8n-nodes-base.respondToWebhook",
      "parameters": {
        "responseData": "binaryData",
        "binaryData": "data",
        "responseHeaders": {
          "entries": [
            {
              "name": "Content-Type",
              "value": "application/pdf"
            }
          ]
        }
      }
    }
  ]
}
```

## Seguridad

Considera implementar:
1. **Autenticación**: Agregar API Key en headers
2. **Rate Limiting**: Limitar descargas por usuario
3. **Validación**: Verificar que el usuario tiene acceso a la factura
4. **Logging**: Registrar todas las descargas para auditoría
