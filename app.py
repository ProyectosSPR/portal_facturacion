"""
Portal de Facturación - Flask + n8n
Arquitectura simplificada:
- Flask: UI + Validaciones básicas + Envío a n8n
- n8n: Lógica de negocio + Postgres + Odoo + Email
"""

import os
import re
import json
import base64
import magic
import psycopg2
from psycopg2.extras import RealDictCursor
import requests
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.utils import secure_filename
from config import Config

# ============================================================================
# CONFIGURACIÓN DE FLASK
# ============================================================================

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Configurar logging detallado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('portal_facturacion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Crear directorio de uploads si no existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


# ============================================================================
# CONEXIÓN A POSTGRESQL (Solo para búsqueda básica)
# ============================================================================

def get_db_connection():
    """Establece conexión con PostgreSQL"""
    try:
        conn = psycopg2.connect(Config.get_postgres_connection_string())
        return conn
    except psycopg2.Error as e:
        app.logger.error(f"Error conectando a PostgreSQL: {e}")
        return None


def buscar_pedido(search_id):
    """
    Busca un pedido por order_id, pack_id o payment_id
    Solo retorna datos básicos para mostrar en el formulario
    """
    conn = get_db_connection()
    if not conn:
        return None

    cursor = None
    try:
        cursor = conn.cursor()

        # Primero intentar por order_id o pack_id (con JOIN a shipment para obtener receiver_id)
        query = """
            SELECT
                o.order_id,
                o.paid_amount,
                o.buyer_nickname,
                o.currency_id,
                o.shipping_id,
                s.receiver_id
            FROM public.orden_ml o
            LEFT JOIN public.shipment s ON o.shipping_id = s.id
            WHERE o.order_id = %s OR o.pack_id = %s
        """
        cursor.execute(query, (search_id, search_id))  # ✅ Pasar search_id DOS veces
        row = cursor.fetchone()

        # Si no encuentra, intentar por payment_id
        if not row:
            query = """
                SELECT
                    o.order_id,
                    o.paid_amount,
                    o.buyer_nickname,
                    o.currency_id,
                    o.shipping_id,
                    s.receiver_id
                FROM public.orden_ml o
                LEFT JOIN public.shipment s ON o.shipping_id = s.id
                WHERE o.payments_0_id = %s
            """
            cursor.execute(query, (search_id,))
            row = cursor.fetchone()

        if row:
            return {
                'order_id': row[0],
                'paid_amount': float(row[1]) if row[1] else 0,
                'buyer_nickname': row[2],
                'currency_id': row[3],
                'shipping_id': row[4],  # ✅ Ahora es shipping_id desde orden_ml
                'receiver_id': row[5]   # ✅ Ahora viene del JOIN con shipment
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
  

# ============================================================================
# VALIDACIONES
# ============================================================================

def validate_pdf_file(file_path):
    """Valida que el archivo sea un PDF real"""
    try:
        file_type = magic.from_file(file_path, mime=True)
        return file_type == 'application/pdf'
    except Exception as e:
        app.logger.error(f"Error validando PDF: {e}")
        return False


def validate_email(email):
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# ============================================================================
# INTEGRACIÓN N8N
# ============================================================================

def enviar_a_n8n(data):
    """
    Envía datos al webhook de n8n
    n8n se encarga de toda la lógica: validar elegibilidad, crear factura, etc.
    """
    logger.info("=" * 80)
    logger.info("INICIANDO ENVÍO DE DATOS A N8N")
    logger.info("=" * 80)

    try:
        # Log del endpoint
        logger.info(f"📡 Endpoint n8n: {Config.N8N_WEBHOOK_URL}")

        # Log del payload (sin datos sensibles completos)
        logger.info("📦 Payload a enviar:")
        logger.info(f"  - Order ID: {data.get('order_id')}")
        logger.info(f"  - Paid Amount: {data.get('paid_amount')} {data.get('currency_id')}")
        logger.info(f"  - Email: {data.get('email')}")
        logger.info(f"  - Phone: {data.get('phone')}")
        logger.info(f"  - CFDI Usage: {data.get('cfdi_usage')}")
        logger.info(f"  - Payment Method: {data.get('payment_method')}")
        logger.info(f"  - CSF Filename: {data.get('csf_pdf', {}).get('filename')}")
        logger.info(f"  - CSF Size: {len(data.get('csf_pdf', {}).get('content', ''))} bytes (base64)")
        logger.info(f"  - Timestamp: {data.get('timestamp')}")
        logger.info(f"  - Source: {data.get('source')}")

        # Serializar payload para log completo (útil para debugging)
        payload_size = len(json.dumps(data))
        logger.info(f"📊 Tamaño total del payload: {payload_size} bytes")

        # Intentar enviar a n8n
        logger.info("🚀 Enviando request POST a n8n...")

        response = requests.post(
            Config.N8N_WEBHOOK_URL,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60  # n8n puede tardar procesando Odoo
        )

        # Log de la respuesta
        logger.info(f"✅ Respuesta recibida de n8n")
        logger.info(f"  - Status Code: {response.status_code}")
        logger.info(f"  - Response Headers: {dict(response.headers)}")

        if response.status_code == 200:
            response_data = response.json()
            logger.info("✅ ÉXITO - n8n procesó la solicitud correctamente")
            logger.info(f"  - Response Body: {json.dumps(response_data, indent=2)}")
            logger.info("=" * 80)
            return True, response_data
        else:
            logger.error(f"❌ ERROR - n8n respondió con error")
            logger.error(f"  - Status Code: {response.status_code}")
            logger.error(f"  - Response Text: {response.text}")
            logger.error("=" * 80)
            return False, {'error': f'Error del servidor: {response.status_code}'}

    except requests.exceptions.Timeout:
        logger.error("❌ TIMEOUT - n8n no respondió a tiempo")
        logger.error(f"  - Timeout configurado: 60 segundos")
        logger.error("  - Posibles causas: n8n caído, procesamiento lento en Odoo, red lenta")
        logger.error("=" * 80)
        return False, {'error': 'El servidor tardó demasiado en responder'}

    except requests.exceptions.ConnectionError as e:
        logger.error("❌ ERROR DE CONEXIÓN - No se pudo conectar con n8n")
        logger.error(f"  - URL: {Config.N8N_WEBHOOK_URL}")
        logger.error(f"  - Error: {str(e)}")
        logger.error("  - Posibles causas: n8n no está ejecutándose, URL incorrecta, firewall")
        logger.error("=" * 80)
        return False, {'error': 'No se pudo conectar con el servicio de facturación'}

    except requests.exceptions.RequestException as e:
        logger.error("❌ ERROR EN REQUEST - Excepción general de requests")
        logger.error(f"  - Tipo de error: {type(e).__name__}")
        logger.error(f"  - Detalle: {str(e)}")
        logger.error("=" * 80)
        return False, {'error': 'No se pudo conectar con el servicio de facturación'}

    except json.JSONDecodeError as e:
        logger.error("❌ ERROR JSON - n8n respondió con JSON inválido")
        logger.error(f"  - Error: {str(e)}")
        logger.error(f"  - Response text: {response.text if 'response' in locals() else 'N/A'}")
        logger.error("=" * 80)
        return False, {'error': 'Respuesta inválida del servidor'}

    except Exception as e:
        logger.error("❌ ERROR INESPERADO en enviar_a_n8n")
        logger.error(f"  - Tipo: {type(e).__name__}")
        logger.error(f"  - Mensaje: {str(e)}")
        logger.exception("  - Stack trace completo:")
        logger.error("=" * 80)
        return False, {'error': f'Error inesperado: {str(e)}'}


# ============================================================================
# RUTAS - INTERFAZ DE USUARIO
# ============================================================================

@app.route('/')
def index():
    """Vista principal: Formulario de búsqueda"""
    return render_template('index.html')


@app.route('/buscar-pedido', methods=['POST'])
def buscar_pedido_route():
    """Busca un pedido y muestra el formulario de facturación"""
    search_id = request.form.get('search_id', '').strip()

    logger.info(f"🔍 Búsqueda de pedido iniciada - ID: {search_id}")

    if not search_id:
        logger.warning("⚠️  Búsqueda sin ID proporcionado")
        flash('Por favor ingresa un ID de pedido o pago.', 'error')
        return redirect(url_for('index'))

    # Buscar pedido en Postgres
    logger.info(f"📊 Consultando base de datos para ID: {search_id}")
    order = buscar_pedido(search_id)

    if not order:
        logger.warning(f"❌ No se encontró pedido con ID: {search_id}")
        flash('No se encontró ningún pedido con ese ID.', 'error')
        return redirect(url_for('index'))

    logger.info(f"✅ Pedido encontrado - Order ID: {order['order_id']}, Amount: {order['paid_amount']}")

    # Guardar en sesión y mostrar formulario
    session['order_data'] = order
    return redirect(url_for('facturar', order_id=order['order_id']))


@app.route('/facturar/<order_id>')
def facturar(order_id):
    """Vista del formulario de facturación"""
    if 'order_data' not in session or session['order_data']['order_id'] != order_id:
        flash('Debes buscar un pedido primero.', 'error')
        return redirect(url_for('index'))

    order = session['order_data']

    return render_template(
        'form_factura.html',
        order=order,
        cfdi_options=Config.CFDI_USAGE_OPTIONS,
        payment_methods=Config.PAYMENT_METHOD_OPTIONS
    )


@app.route('/procesar-factura', methods=['POST'])
def procesar_factura():
    """
    Procesa el formulario y envía todo a n8n
    n8n se encarga de: validar elegibilidad, crear factura en Odoo, enviar email
    """
    logger.info("=" * 80)
    logger.info("📝 PROCESANDO SOLICITUD DE FACTURA ODOO")
    logger.info("=" * 80)

    # Validar sesión
    if 'order_data' not in session:
        logger.error("❌ Sesión expirada o no existe")
        flash('Sesión expirada. Busca el pedido nuevamente.', 'error')
        return redirect(url_for('index'))

    order = session['order_data']
    logger.info(f"📦 Order ID: {order['order_id']}")

    # ========================================================================
    # VALIDAR ARCHIVO PDF
    # ========================================================================
    logger.info("📄 Validando archivo PDF...")

    if 'csf_file' not in request.files:
        logger.error("❌ No se encontró archivo en el request")
        flash('Debes adjuntar la Constancia de Situación Fiscal (PDF).', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    file = request.files['csf_file']
    if file.filename == '':
        logger.error("❌ Archivo sin nombre")
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    logger.info(f"  - Nombre archivo: {file.filename}")

    if not file.filename.lower().endswith('.pdf'):
        logger.error(f"❌ Archivo no es PDF: {file.filename}")
        flash('El archivo debe ser un PDF.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Guardar temporalmente para validar
    filename = secure_filename(f"{order['order_id']}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    logger.info(f"  - Guardando en: {file_path}")
    file.save(file_path)

    # Validar que sea PDF real
    logger.info("  - Validando tipo MIME...")
    if not validate_pdf_file(file_path):
        os.remove(file_path)
        logger.error("❌ Archivo no es un PDF válido (validación MIME falló)")
        flash('El archivo no es un PDF válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    logger.info("✅ PDF validado correctamente")

    # ========================================================================
    # VALIDAR DATOS DEL FORMULARIO
    # ========================================================================
    logger.info("📋 Validando datos del formulario...")

    cfdi_usage = request.form.get('cfdi_usage', '').strip()
    payment_method = request.form.get('payment_method', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    monto_pagado = request.form.get('monto_pagado', '').strip()

    logger.info(f"  - CFDI Usage: {cfdi_usage}")
    logger.info(f"  - Payment Method: {payment_method}")
    logger.info(f"  - Email: {email}")
    logger.info(f"  - Phone: {phone}")
    logger.info(f"  - Monto Pagado: {monto_pagado}")

    # Validaciones básicas
    if not all([cfdi_usage, payment_method, email, monto_pagado]):
        os.remove(file_path)
        logger.error("❌ Campos obligatorios faltantes")
        flash('Todos los campos obligatorios deben ser completados.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    if not validate_email(email):
        os.remove(file_path)
        logger.error(f"❌ Email inválido: {email}")
        flash('El formato del correo electrónico no es válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    try:
        monto_pagado_float = float(monto_pagado)
        logger.info(f"  - Monto convertido: {monto_pagado_float}")
    except ValueError:
        os.remove(file_path)
        logger.error(f"❌ Monto inválido (no numérico): {monto_pagado}")
        flash('El monto pagado debe ser un número válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Validar monto (tolerancia de 0.01)
    diferencia = abs(monto_pagado_float - order['paid_amount'])
    logger.info(f"  - Validando monto: {monto_pagado_float} vs {order['paid_amount']} (diff: {diferencia})")

    if diferencia > 0.01:
        os.remove(file_path)
        logger.error(f"❌ Monto no coincide - Esperado: {order['paid_amount']}, Recibido: {monto_pagado_float}")
        flash(f"El monto ingresado no coincide con el monto del pedido (${order['paid_amount']}).", 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    logger.info("✅ Todos los datos del formulario son válidos")

    # ========================================================================
    # PREPARAR DATOS PARA N8N
    # ========================================================================
    logger.info("📦 Preparando payload para n8n...")

    # Convertir PDF a base64
    logger.info("  - Convirtiendo PDF a base64...")
    with open(file_path, 'rb') as f:
        pdf_content = base64.b64encode(f.read()).decode('utf-8')
    logger.info(f"  - PDF codificado: {len(pdf_content)} caracteres")

    # Payload para n8n
    payload = {
        # Datos del pedido
        'order_id': order['order_id'],
        'paid_amount': order['paid_amount'],
        'currency_id': order.get('currency_id', 'MXN'),

        # Datos del comprador (para crear usuario en portal)
        'receiver_id': order.get('receiver_id'),
        'shipping_id': order.get('shipping_id'),  # ✅ Corregido: shipping_id no shipment_id
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

    logger.info("✅ Payload preparado correctamente")

    # Eliminar archivo temporal
    logger.info(f"🗑️  Eliminando archivo temporal: {file_path}")
    os.remove(file_path)

    # ========================================================================
    # ENVIAR A N8N
    # ========================================================================

    success, response = enviar_a_n8n(payload)

    if not success:
        error_msg = response.get('error', 'Error desconocido')
        logger.error(f"❌ Falló el envío a n8n: {error_msg}")
        flash(f'No se pudo procesar la solicitud: {error_msg}', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Procesar respuesta de n8n
    logger.info("📨 Procesando respuesta de n8n...")

    if response.get('success'):
        # Limpiar sesión
        session.pop('order_data', None)

        mensaje = response.get('message',
            f'¡Solicitud enviada! Recibirás tu factura en: {email}')
        logger.info(f"✅ ÉXITO TOTAL - {mensaje}")
        flash(mensaje, 'success')
        return redirect(url_for('exito', order_id=order['order_id']))
    else:
        # n8n retornó error (pedido no elegible, error en Odoo, etc.)
        error_msg = response.get('message', 'Error al procesar la factura')
        logger.error(f"❌ n8n reportó error: {error_msg}")
        flash(error_msg, 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))


@app.route('/exito/<order_id>')
def exito(order_id):
    """Página de confirmación exitosa"""
    return render_template('exito.html', order_id=order_id)


# ============================================================================
# ENDPOINTS - CALLBACKS DESDE N8N
# ============================================================================

@app.route('/webhook/factura-procesada', methods=['POST'])
def webhook_factura_procesada():
    """
    n8n llama este endpoint cuando termina de procesar
    Útil para notificaciones en tiempo real, actualizar UI, etc.

    Payload de n8n:
    {
        "order_id": "123456",
        "status": "success|error",
        "invoice_id": "INV/2024/001",
        "message": "Factura creada",
        "pdf_url": "https://..."  // opcional
    }
    """
    try:
        data = request.get_json()

        if not data or 'order_id' not in data:
            return jsonify({'error': 'Datos inválidos'}), 400

        order_id = data['order_id']
        status = data.get('status')

        # Loguear para tracking
        app.logger.info(f"Webhook n8n - Order {order_id}: {status}")

        # Aquí podrías:
        # - Guardar en una tabla de logs
        # - Enviar notificación WebSocket al cliente
        # - Actualizar caché
        # - etc.

        return jsonify({
            'success': True,
            'message': 'Webhook recibido'
        }), 200

    except Exception as e:
        app.logger.error(f"Error en webhook: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/webhook/enviar-pdf', methods=['POST'])
def webhook_enviar_pdf():
    """
    n8n puede enviar PDFs generados (facturas timbradas, etc.)

    Payload de n8n:
    {
        "order_id": "123456",
        "pdf_content": "base64...",
        "filename": "factura.pdf",
        "type": "factura|complemento"
    }
    """
    try:
        data = request.get_json()

        if not data or 'pdf_content' not in data:
            return jsonify({'error': 'Datos inválidos'}), 400

        order_id = data.get('order_id')
        pdf_base64 = data['pdf_content']
        filename = data.get('filename', 'documento.pdf')

        # Decodificar y guardar PDF
        pdf_bytes = base64.b64decode(pdf_base64)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"received_{filename}")

        with open(save_path, 'wb') as f:
            f.write(pdf_bytes)

        app.logger.info(f"PDF recibido de n8n: {filename} para orden {order_id}")

        return jsonify({
            'success': True,
            'message': 'PDF recibido y guardado',
            'path': save_path
        }), 200

    except Exception as e:
        app.logger.error(f"Error recibiendo PDF: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/webhook/actualizar-estado', methods=['POST'])
def webhook_actualizar_estado():
    """
    Endpoint genérico para que n8n notifique cambios de estado

    Payload de n8n:
    {
        "order_id": "123456",
        "estado": "procesando|timbrada|enviada|error",
        "detalles": "...",
        "timestamp": "2024-01-01T12:00:00"
    }
    """
    try:
        data = request.get_json()

        if not data or 'order_id' not in data:
            return jsonify({'error': 'Datos inválidos'}), 400

        order_id = data['order_id']
        estado = data.get('estado', 'unknown')
        detalles = data.get('detalles', '')

        app.logger.info(f"Estado actualizado - Orden {order_id}: {estado} - {detalles}")

        # Aquí podrías guardar en una tabla de estados:
        # INSERT INTO facturacion_estados (order_id, estado, detalles) VALUES (...)

        return jsonify({
            'success': True,
            'message': 'Estado actualizado'
        }), 200

    except Exception as e:
        app.logger.error(f"Error actualizando estado: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# MANEJO DE ERRORES
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/') or request.path.startswith('/webhook/'):
        return jsonify({'error': 'Endpoint no encontrado'}), 404
    return render_template('error.html', message='Página no encontrada'), 404


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/') or request.path.startswith('/webhook/'):
        return jsonify({'error': 'Error interno del servidor'}), 500
    return render_template('error.html', message='Error interno del servidor'), 500


# ============================================================================
# PORTAL DE USUARIOS - SISTEMA DE LOGIN
# ============================================================================

def login_required(f):
    """Decorador para rutas que requieren autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('portal_login'))
        return f(*args, **kwargs)
    return decorated_function


def registrar_acceso(usuario_id, email, receiver_id, tipo_evento, exitoso=True, mensaje=''):
    """Registra en historial_accesos"""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        query = """
            INSERT INTO historial_accesos
            (usuario_id, email, receiver_id, tipo_evento, ip_address, user_agent, exitoso, mensaje)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            usuario_id,
            email,
            receiver_id,
            tipo_evento,
            request.remote_addr,
            request.user_agent.string[:500] if request.user_agent else None,
            exitoso,
            mensaje
        ))
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error registrando acceso: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def actualizar_ultimo_acceso(usuario_id):
    """Actualiza el timestamp de último acceso"""
    conn = get_db_connection()
    if not conn:
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE usuarios_portal SET ultimo_acceso = NOW() WHERE id = %s",
            (usuario_id,)
        )
        conn.commit()
    except Exception as e:
        app.logger.error(f"Error actualizando último acceso: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================================
# RUTAS - AUTENTICACIÓN
# ============================================================================

@app.route('/portal/login')
def portal_login():
    """Página de login del portal"""
    if 'usuario_id' in session:
        return redirect(url_for('portal_dashboard'))

    return render_template('portal/login.html')


@app.route('/portal/login', methods=['POST'])
def portal_login_post():
    """Procesa el login"""
    email = request.form.get('email', '').strip().lower()
    receiver_id = request.form.get('receiver_id', '').strip()

    if not email or not receiver_id:
        flash('Por favor ingresa tu email y número de cliente.', 'error')
        return redirect(url_for('portal_login'))

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión. Intenta nuevamente.', 'error')
        return redirect(url_for('portal_login'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Buscar usuario
        query = """
            SELECT id, receiver_id, email, nombre, activo, bloqueado_hasta, intentos_fallidos
            FROM usuarios_portal
            WHERE email = %s AND receiver_id = %s
        """
        cursor.execute(query, (email, receiver_id))
        usuario = cursor.fetchone()

        if not usuario:
            registrar_acceso(None, email, receiver_id, 'login_fallido', False, 'Credenciales incorrectas')
            flash('Email o número de cliente incorrecto.', 'error')
            return redirect(url_for('portal_login'))

        # Verificar si está bloqueado
        if usuario['bloqueado_hasta'] and usuario['bloqueado_hasta'] > datetime.now():
            tiempo_restante = (usuario['bloqueado_hasta'] - datetime.now()).seconds // 60
            flash(f'Cuenta bloqueada temporalmente. Intenta en {tiempo_restante} minutos.', 'error')
            return redirect(url_for('portal_login'))

        # Verificar si está activo
        if not usuario['activo']:
            registrar_acceso(usuario['id'], email, receiver_id, 'login_fallido', False, 'Cuenta inactiva')
            flash('Tu cuenta ha sido desactivada. Contacta a soporte.', 'error')
            return redirect(url_for('portal_login'))

        # Login exitoso
        session['usuario_id'] = usuario['id']
        session['email'] = usuario['email']
        session['nombre'] = usuario['nombre']
        session['receiver_id'] = usuario['receiver_id']
        session['login_time'] = datetime.now().isoformat()

        # Resetear intentos fallidos
        cursor.execute(
            "UPDATE usuarios_portal SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s",
            (usuario['id'],)
        )
        conn.commit()

        registrar_acceso(usuario['id'], email, receiver_id, 'login_exitoso', True, 'Login exitoso')
        actualizar_ultimo_acceso(usuario['id'])

        flash(f'Bienvenido, {usuario["nombre"]}!', 'success')
        return redirect(url_for('portal_dashboard'))

    except Exception as e:
        app.logger.error(f"Error en login: {e}")
        flash('Error al iniciar sesión. Intenta nuevamente.', 'error')
        return redirect(url_for('portal_login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/logout')
def portal_logout():
    """Cerrar sesión"""
    if 'usuario_id' in session:
        registrar_acceso(
            session.get('usuario_id'),
            session.get('email'),
            session.get('receiver_id'),
            'logout',
            True,
            'Logout exitoso'
        )

    session.clear()
    flash('Sesión cerrada exitosamente.', 'info')
    return redirect(url_for('portal_login'))


# ============================================================================
# RUTAS - DASHBOARD
# ============================================================================

@app.route('/portal/dashboard')
@login_required
def portal_dashboard():
    """Dashboard principal del usuario"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_login'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener facturas del usuario
        query = """
            SELECT
                f.id,
                f.order_id,
                f.invoice_name,
                f.amount,
                f.currency_id,
                f.status,
                f.payment_status,
                f.paid_amount,
                f.payment_date,
                f.pdf_url,
                f.xml_url,
                f.observaciones_contabilidad,
                f.notas_cliente,
                f.created_at,
                f.updated_at
            FROM facturas f
            WHERE f.usuario_id = %s
            ORDER BY f.created_at DESC
        """
        cursor.execute(query, (usuario_id,))
        facturas = cursor.fetchall()

        # Obtener notificaciones no leídas
        query_notif = """
            SELECT COUNT(*) as count
            FROM notificaciones
            WHERE usuario_id = %s AND leida = FALSE
        """
        cursor.execute(query_notif, (usuario_id,))
        notificaciones_count = cursor.fetchone()['count']

        # Estadísticas
        stats = {
            'total_facturas': len(facturas),
            'monto_total': sum(f['amount'] for f in facturas),
            'facturas_pendientes': sum(1 for f in facturas if f['payment_status'] == 'pending'),
            'facturas_pagadas': sum(1 for f in facturas if f['payment_status'] == 'paid'),
        }

        return render_template(
            'portal/dashboard.html',
            facturas=facturas,
            stats=stats,
            notificaciones_count=notificaciones_count
        )

    except Exception as e:
        app.logger.error(f"Error en dashboard: {e}")
        flash('Error al cargar el dashboard.', 'error')
        return redirect(url_for('portal_login'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/factura/<int:factura_id>')
@login_required
def portal_factura_detalle(factura_id):
    """Ver detalle de una factura específica"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener factura (solo si pertenece al usuario)
        query = """
            SELECT
                f.*,
                u.nombre as usuario_nombre,
                u.email as usuario_email
            FROM facturas f
            INNER JOIN usuarios_portal u ON f.usuario_id = u.id
            WHERE f.id = %s AND f.usuario_id = %s
        """
        cursor.execute(query, (factura_id, usuario_id))
        factura = cursor.fetchone()

        if not factura:
            flash('Factura no encontrada.', 'error')
            return redirect(url_for('portal_dashboard'))

        return render_template('portal/factura_detalle.html', factura=factura)

    except Exception as e:
        app.logger.error(f"Error obteniendo factura: {e}")
        flash('Error al cargar la factura.', 'error')
        return redirect(url_for('portal_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/factura/<int:factura_id>/pdf')
@login_required
def portal_descargar_pdf(factura_id):
    """Descargar PDF de factura"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verificar que la factura pertenece al usuario
        query = """
            SELECT pdf_url, order_id
            FROM facturas
            WHERE id = %s AND usuario_id = %s
        """
        cursor.execute(query, (factura_id, usuario_id))
        factura = cursor.fetchone()

        if not factura:
            flash('Factura no encontrada.', 'error')
            return redirect(url_for('portal_dashboard'))

        if not factura['pdf_url']:
            flash('PDF no disponible aún.', 'warning')
            return redirect(url_for('portal_factura_detalle', factura_id=factura_id))

        # Verificar si existe el archivo
        file_path = factura['pdf_url']
        if os.path.exists(file_path):
            return send_file(
                file_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f"factura_{factura['order_id']}.pdf"
            )
        else:
            flash('Archivo no encontrado.', 'error')
            return redirect(url_for('portal_factura_detalle', factura_id=factura_id))

    except Exception as e:
        app.logger.error(f"Error descargando PDF: {e}")
        flash('Error al descargar PDF.', 'error')
        return redirect(url_for('portal_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/factura/<int:factura_id>/xml')
@login_required
def portal_descargar_xml(factura_id):
    """Descargar XML de factura"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Verificar que la factura pertenece al usuario
        query = """
            SELECT xml_url, order_id
            FROM facturas
            WHERE id = %s AND usuario_id = %s
        """
        cursor.execute(query, (factura_id, usuario_id))
        factura = cursor.fetchone()

        if not factura:
            flash('Factura no encontrada.', 'error')
            return redirect(url_for('portal_dashboard'))

        if not factura['xml_url']:
            flash('XML no disponible aún.', 'warning')
            return redirect(url_for('portal_factura_detalle', factura_id=factura_id))

        # Verificar si existe el archivo
        file_path = factura['xml_url']
        if os.path.exists(file_path):
            return send_file(
                file_path,
                mimetype='application/xml',
                as_attachment=True,
                download_name=f"factura_{factura['order_id']}.xml"
            )
        else:
            flash('Archivo no encontrado.', 'error')
            return redirect(url_for('portal_factura_detalle', factura_id=factura_id))

    except Exception as e:
        app.logger.error(f"Error descargando XML: {e}")
        flash('Error al descargar XML.', 'error')
        return redirect(url_for('portal_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    # Desarrollo con auto-reload
    logger.info("🚀 Iniciando Portal de Facturación")
    logger.info(f"  - Modo: DEBUG")
    logger.info(f"  - Host: 0.0.0.0")
    logger.info(f"  - Port: 5000")
    logger.info(f"  - Auto-reload: ACTIVADO (detecta cambios automáticamente)")
    logger.info(f"  - Extra files: Monitoreando config.py y templates/")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000,
        use_reloader=True,  # Detecta cambios automáticamente
        extra_files=['config.py']  # Monitorear archivos adicionales
    )
