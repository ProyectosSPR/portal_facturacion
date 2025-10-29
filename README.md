# Portal de Facturación - Mercado Libre

Portal web desarrollado en Flask para que clientes de Mercado Libre soliciten sus facturas. Utiliza n8n como orquestador para integrar con Odoo 16 y automatizar todo el proceso de facturación.

## 🏗️ Arquitectura

```
┌─────────┐      ┌─────────┐      ┌─────────┐      ┌─────────┐
│ Usuario │ ───► │  Flask  │ ───► │   n8n   │ ───► │  Odoo   │
│   Web   │      │(UI/Form)│      │(Lógica) │      │ (ERP)   │
└─────────┘      └────┬────┘      └────┬────┘      └─────────┘
                      │                 │
                      ▼                 ▼
                 ┌─────────┐      ┌─────────┐
                 │Postgres │      │  Email  │
                 │(ML Data)│      │ (SMTP)  │
                 └─────────┘      └─────────┘
```

### Responsabilidades

- **Flask**:
  - Interfaz de usuario (formularios HTML)
  - Validaciones básicas del frontend
  - Recepción de archivos PDF
  - Envío de datos a n8n
  - Recepción de callbacks

- **n8n**:
  - Validación de elegibilidad del pedido (Reglas A y B)
  - Consultas a PostgreSQL (órdenes, pagos, envíos)
  - Creación de facturas en Odoo
  - Envío de emails con PDFs
  - Orquestación completa del flujo

- **PostgreSQL**: Datos de Mercado Libre (órdenes, pagos, envíos)
- **Odoo 16**: ERP para facturación electrónica

## 📋 Requisitos

- Python 3.8+
- PostgreSQL (con datos de Mercado Libre)
- n8n (self-hosted o cloud)
- Odoo 16 con localización mexicana (l10n_mx)
- python-magic (requiere libmagic):
  - Ubuntu/Debian: `sudo apt-get install libmagic1`
  - macOS: `brew install libmagic`
  - Windows: Descargar DLL desde [aquí](https://github.com/ahupp/python-magic#dependencies)

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
cd /home/dml/portal_facturacion
```

### 2. Crear entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

```bash
cp .env.example .env
nano .env  # Editar con tus valores reales
```

Variables clave a configurar:
- `SECRET_KEY`: Genera una clave aleatoria para Flask
- `POSTGRES_*`: Credenciales de tu base de datos de Mercado Libre
- `N8N_WEBHOOK_URL`: URL del webhook de n8n (ver siguiente sección)

### 5. Configurar n8n

1. **Importar o crear workflow** siguiendo la guía: [N8N_WORKFLOW_GUIDE.md](N8N_WORKFLOW_GUIDE.md)

2. **Activar el webhook** en n8n y copiar la URL

3. **Configurar credenciales** en n8n:
   - PostgreSQL (lectura a base de ML)
   - Odoo (API para crear facturas)
   - Email/SMTP (envío de facturas)

4. **Configurar la URL del webhook** en tu `.env`:
   ```
   N8N_WEBHOOK_URL=https://your-n8n.com/webhook/facturacion
   ```

### 6. Verificar estructura de base de datos

Asegúrate de que existan las tablas:
- `public.orden_ml` (con campos: `order_id`, `shipping_id`, `payments_0_id`, `record_odoo`, etc.)
- `public.shipment` (con campo: `logistic_type`)
- `public.pagos_mercadopago` (con campos de liberación de pagos)

### 7. Ejecutar la aplicación

**Desarrollo:**
```bash
python app.py
```

**Producción (con Gunicorn):**
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

**Con systemd (Linux):**
```bash
sudo nano /etc/systemd/system/portal-facturacion.service
```

```ini
[Unit]
Description=Portal de Facturación Flask
After=network.target

[Service]
User=dml
WorkingDirectory=/home/dml/portal_facturacion
Environment="PATH=/home/dml/portal_facturacion/venv/bin"
ExecStart=/home/dml/portal_facturacion/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl start portal-facturacion
sudo systemctl enable portal-facturacion
```

## 📖 Uso

### Flujo del Usuario

1. **Buscar Pedido** (`/`)
   - Ingresar ID de pedido o ID de pago de Mercado Libre
   - El sistema verifica que exista en la base de datos

2. **Completar Formulario** (`/facturar/<order_id>`)
   - Subir Constancia de Situación Fiscal (PDF)
   - Ingresar email y teléfono
   - Seleccionar Uso del CFDI y Forma de Pago
   - Confirmar monto

3. **Procesar Solicitud** (`/procesar-factura`)
   - Flask envía datos + PDF a n8n
   - n8n valida elegibilidad, crea factura en Odoo y envía email
   - Usuario recibe confirmación

4. **Confirmación** (`/exito/<order_id>`)
   - Se muestra mensaje de éxito
   - Factura enviada por email

### Reglas de Negocio

#### Regla A: Mercado Envíos Full/Agencia
- **Logistic Type**: `fulfillment` o `cross_docking`
- **Elegibilidad**: Inmediata (no requiere pago liberado)
- **Proceso**: Factura marcada como "Pendiente Timbrado (Full)"

#### Regla B: Envío Externo
- **Logistic Type**: Otros tipos de envío
- **Elegibilidad**: Requiere pago liberado por Mercado Libre
- **Proceso**: Factura normal, puede marcarse como pagada automáticamente

## 🔌 API Endpoints

### Endpoints de Usuario (HTML)

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/` | GET | Formulario de búsqueda |
| `/buscar-pedido` | POST | Busca un pedido |
| `/facturar/<order_id>` | GET | Formulario de facturación |
| `/procesar-factura` | POST | Envía solicitud a n8n |
| `/exito/<order_id>` | GET | Confirmación exitosa |

### Webhooks para n8n (JSON)

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/webhook/factura-procesada` | POST | Notifica factura creada |
| `/webhook/enviar-pdf` | POST | Recibe PDFs de n8n |
| `/webhook/actualizar-estado` | POST | Actualiza estados |

## 📦 Estructura del Proyecto

```
portal_facturacion/
├── app.py                      # Aplicación principal de Flask
├── config.py                   # Configuración y variables
├── requirements.txt            # Dependencias de Python
├── .env.example               # Plantilla de variables de entorno
├── .env                       # Variables de entorno (no versionar)
├── README.md                  # Este archivo
├── N8N_WORKFLOW_GUIDE.md      # Guía completa del workflow n8n
├── templates/                 # Plantillas HTML
│   ├── base.html             # Layout base
│   ├── index.html            # Búsqueda de pedido
│   ├── form_factura.html     # Formulario de facturación
│   ├── exito.html            # Confirmación
│   └── error.html            # Página de error
└── uploads/                   # Archivos temporales (crear automáticamente)
```

## 🔐 Seguridad

### Recomendaciones

1. **Variables de Entorno**: Nunca subir `.env` a control de versiones
2. **HTTPS**: Usar HTTPS en producción (con nginx + Let's Encrypt)
3. **Validación de Archivos**: Flask valida tipo MIME de PDFs
4. **Límite de Tamaño**: Máximo 16MB por archivo
5. **Rate Limiting**: Considerar implementar rate limiting (Flask-Limiter)
6. **Webhook Security**: Validar origen de webhooks de n8n (IP whitelist o tokens)

### Ejemplo nginx con HTTPS

```nginx
server {
    listen 80;
    server_name facturacion.tudominio.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name facturacion.tudominio.com;

    ssl_certificate /etc/letsencrypt/live/facturacion.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/facturacion.tudominio.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🐛 Troubleshooting

### Error: "No se pudo conectar con el servicio de facturación"

- Verificar que n8n esté corriendo y accesible
- Verificar la URL del webhook en `.env`
- Revisar logs de n8n para ver si está recibiendo la petición

### Error: "Error conectando a PostgreSQL"

- Verificar credenciales en `.env`
- Verificar que PostgreSQL esté corriendo: `sudo systemctl status postgresql`
- Verificar que el usuario tenga permisos de lectura en las tablas

### Error: "El archivo no es un PDF válido"

- Verificar que libmagic esté instalado
- Ubuntu: `sudo apt-get install libmagic1`
- Probar con otro PDF

### El workflow de n8n no se ejecuta

- Verificar que el webhook esté activado en n8n
- Revisar los logs de ejecución en n8n
- Verificar las credenciales de Postgres y Odoo en n8n

## 📊 Monitoreo

### Logs de Flask

```bash
# Ver logs en tiempo real
tail -f /var/log/portal-facturacion.log

# Si usas systemd
journalctl -u portal-facturacion -f
```

### Logs de n8n

- Acceder a la interfaz de n8n
- Ir a "Executions" para ver historial
- Verificar nodos que fallaron

## 🔄 Actualizaciones

### Actualizar dependencias

```bash
source venv/bin/activate
pip install --upgrade -r requirements.txt
```

### Reiniciar servicio

```bash
sudo systemctl restart portal-facturacion
```

## 📝 Desarrollo

### Agregar nuevos endpoints

1. Agregar ruta en `app.py`
2. Crear template HTML si es necesario
3. Actualizar documentación

### Modificar lógica de negocio

**No modificar `app.py`** para cambios de lógica. Toda la lógica de negocio está en n8n.

Solo modificar Flask si:
- Cambias la UI
- Agregas validaciones del lado del cliente
- Cambias estructura de datos enviados a n8n

## 🤝 Contribuciones

Este proyecto es interno. Para cambios:

1. Crear branch: `git checkout -b feature/nueva-funcionalidad`
2. Hacer cambios y commit
3. Push y crear Pull Request

## 📄 Licencia

Uso interno de la empresa.

## 📞 Soporte

Para problemas o dudas:
- Revisar esta documentación
- Revisar [N8N_WORKFLOW_GUIDE.md](N8N_WORKFLOW_GUIDE.md)
- Contactar al equipo de desarrollo

---

**Última actualización**: 2024
**Versión**: 1.0.0
