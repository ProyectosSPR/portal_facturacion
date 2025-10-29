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
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from werkzeug.utils import secure_filename
from config import Config

# ============================================================================
# CONFIGURACIÓN DE FLASK
# ============================================================================

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

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
    Busca un pedido por order_id o payment_id
    Solo retorna datos básicos para mostrar en el formulario
    """
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Primero intentar por order_id
        query = """
            SELECT order_id, paid_amount, buyer_nickname, currency_id
            FROM public.orden_ml
            WHERE order_id = %s or pack_id = %s
        """
        cursor.execute(query, (search_id,))
        row = cursor.fetchone()

        # Si no encuentra, intentar por payment_id
        if not row:
            query = """
                SELECT order_id, paid_amount, buyer_nickname, currency_id
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
                'currency_id': row[3]
            }
        return None

    except psycopg2.Error as e:
        app.logger.error(f"Error buscando pedido: {e}")
        return None
    finally:
        cursor.close()
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
    try:
        response = requests.post(
            Config.N8N_WEBHOOK_URL,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=60  # n8n puede tardar procesando Odoo
        )

        if response.status_code == 200:
            return True, response.json()
        else:
            app.logger.error(f"Error n8n: {response.status_code} - {response.text}")
            return False, {'error': f'Error del servidor: {response.status_code}'}

    except requests.exceptions.Timeout:
        app.logger.error("Timeout esperando respuesta de n8n")
        return False, {'error': 'El servidor tardó demasiado en responder'}
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error conectando con n8n: {e}")
        return False, {'error': 'No se pudo conectar con el servicio de facturación'}


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

    if not search_id:
        flash('Por favor ingresa un ID de pedido o pago.', 'error')
        return redirect(url_for('index'))

    # Buscar pedido en Postgres
    order = buscar_pedido(search_id)

    if not order:
        flash('No se encontró ningún pedido con ese ID.', 'error')
        return redirect(url_for('index'))

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
    # Validar sesión
    if 'order_data' not in session:
        flash('Sesión expirada. Busca el pedido nuevamente.', 'error')
        return redirect(url_for('index'))

    order = session['order_data']

    # ========================================================================
    # VALIDAR ARCHIVO PDF
    # ========================================================================
    if 'csf_file' not in request.files:
        flash('Debes adjuntar la Constancia de Situación Fiscal (PDF).', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    file = request.files['csf_file']
    if file.filename == '':
        flash('No se seleccionó ningún archivo.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    if not file.filename.lower().endswith('.pdf'):
        flash('El archivo debe ser un PDF.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Guardar temporalmente para validar
    filename = secure_filename(f"{order['order_id']}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    # Validar que sea PDF real
    if not validate_pdf_file(file_path):
        os.remove(file_path)
        flash('El archivo no es un PDF válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # ========================================================================
    # VALIDAR DATOS DEL FORMULARIO
    # ========================================================================
    cfdi_usage = request.form.get('cfdi_usage', '').strip()
    payment_method = request.form.get('payment_method', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    monto_pagado = request.form.get('monto_pagado', '').strip()

    # Validaciones básicas
    if not all([cfdi_usage, payment_method, email, monto_pagado]):
        os.remove(file_path)
        flash('Todos los campos obligatorios deben ser completados.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    if not validate_email(email):
        os.remove(file_path)
        flash('El formato del correo electrónico no es válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    try:
        monto_pagado_float = float(monto_pagado)
    except ValueError:
        os.remove(file_path)
        flash('El monto pagado debe ser un número válido.', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Validar monto (tolerancia de 0.01)
    if abs(monto_pagado_float - order['paid_amount']) > 0.01:
        os.remove(file_path)
        flash(f"El monto ingresado no coincide con el monto del pedido (${order['paid_amount']}).", 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # ========================================================================
    # PREPARAR DATOS PARA N8N
    # ========================================================================

    # Convertir PDF a base64
    with open(file_path, 'rb') as f:
        pdf_content = base64.b64encode(f.read()).decode('utf-8')

    # Payload para n8n
    payload = {
        # Datos del pedido
        'order_id': order['order_id'],
        'paid_amount': order['paid_amount'],
        'currency_id': order.get('currency_id', 'MXN'),

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

    # Eliminar archivo temporal
    os.remove(file_path)

    # ========================================================================
    # ENVIAR A N8N
    # ========================================================================

    success, response = enviar_a_n8n(payload)

    if not success:
        error_msg = response.get('error', 'Error desconocido')
        flash(f'No se pudo procesar la solicitud: {error_msg}', 'error')
        return redirect(url_for('facturar', order_id=order['order_id']))

    # Procesar respuesta de n8n
    if response.get('success'):
        # Limpiar sesión
        session.pop('order_data', None)

        mensaje = response.get('message',
            f'¡Solicitud enviada! Recibirás tu factura en: {email}')
        flash(mensaje, 'success')
        return redirect(url_for('exito', order_id=order['order_id']))
    else:
        # n8n retornó error (pedido no elegible, error en Odoo, etc.)
        error_msg = response.get('message', 'Error al procesar la factura')
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
# PUNTO DE ENTRADA
# ============================================================================

if __name__ == '__main__':
    # Desarrollo
    app.run(debug=True, host='0.0.0.0', port=5000)
