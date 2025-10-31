"""
MÓDULO ADICIONAL PARA APP.PY
Portal de Usuarios - Sistema de Login y Dashboard

INSTRUCCIONES:
1. Agregar estas rutas a app.py
2. Crear las plantillas HTML correspondientes
3. Configurar secret_key para sesiones
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import session, redirect, url_for, flash, request, render_template, jsonify, send_file
import psycopg2
from psycopg2.extras import RealDictCursor


# ============================================================================
# DECORADORES
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


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_db_connection():
    """
    Reutiliza la función del app.py principal
    """
    from app import get_db_connection as get_conn
    return get_conn()


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


@app.route('/portal/notificaciones')
@login_required
def portal_notificaciones():
    """Ver notificaciones del usuario"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Obtener todas las notificaciones
        query = """
            SELECT
                n.*,
                f.order_id,
                f.invoice_name
            FROM notificaciones n
            LEFT JOIN facturas f ON n.factura_id = f.id
            WHERE n.usuario_id = %s
            ORDER BY n.created_at DESC
            LIMIT 50
        """
        cursor.execute(query, (usuario_id,))
        notificaciones = cursor.fetchall()

        return render_template('portal/notificaciones.html', notificaciones=notificaciones)

    except Exception as e:
        app.logger.error(f"Error obteniendo notificaciones: {e}")
        flash('Error al cargar notificaciones.', 'error')
        return redirect(url_for('portal_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/notificacion/<int:notif_id>/marcar-leida', methods=['POST'])
@login_required
def portal_marcar_notificacion_leida(notif_id):
    """Marcar notificación como leída"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Error de conexión'}), 500

    try:
        cursor = conn.cursor()

        query = """
            UPDATE notificaciones
            SET leida = TRUE, fecha_leida = NOW()
            WHERE id = %s AND usuario_id = %s
        """
        cursor.execute(query, (notif_id, usuario_id))
        conn.commit()

        return jsonify({'success': True})

    except Exception as e:
        app.logger.error(f"Error marcando notificación: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================================
# RUTAS - DESCARGA DE ARCHIVOS
# ============================================================================

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

        if not factura or not factura['pdf_url']:
            flash('PDF no disponible.', 'error')
            return redirect(url_for('portal_dashboard'))

        # Aquí deberías implementar la lógica para servir el archivo
        # Dependiendo de dónde estén almacenados (filesystem, S3, etc.)

        # Ejemplo si está en filesystem:
        from flask import send_file
        import os

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

        if not factura or not factura['xml_url']:
            flash('XML no disponible.', 'error')
            return redirect(url_for('portal_dashboard'))

        # Similar a PDF
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
# RUTAS - PERFIL DE USUARIO
# ============================================================================

@app.route('/portal/perfil')
@login_required
def portal_perfil():
    """Ver y editar perfil del usuario"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_dashboard'))

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT *
            FROM usuarios_portal
            WHERE id = %s
        """
        cursor.execute(query, (usuario_id,))
        usuario = cursor.fetchone()

        # Obtener historial de accesos recientes
        query_historial = """
            SELECT *
            FROM historial_accesos
            WHERE usuario_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """
        cursor.execute(query_historial, (usuario_id,))
        historial = cursor.fetchall()

        return render_template(
            'portal/perfil.html',
            usuario=usuario,
            historial=historial
        )

    except Exception as e:
        app.logger.error(f"Error obteniendo perfil: {e}")
        flash('Error al cargar perfil.', 'error')
        return redirect(url_for('portal_dashboard'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/portal/perfil/actualizar', methods=['POST'])
@login_required
def portal_actualizar_perfil():
    """Actualizar datos del perfil"""
    usuario_id = session['usuario_id']

    nombre = request.form.get('nombre', '').strip()
    telefono = request.form.get('telefono', '').strip()
    rfc = request.form.get('rfc', '').strip().upper()
    razon_social = request.form.get('razon_social', '').strip()
    domicilio_fiscal = request.form.get('domicilio_fiscal', '').strip()

    conn = get_db_connection()
    if not conn:
        flash('Error de conexión.', 'error')
        return redirect(url_for('portal_perfil'))

    try:
        cursor = conn.cursor()

        query = """
            UPDATE usuarios_portal
            SET
                nombre = %s,
                telefono = %s,
                rfc = %s,
                razon_social = %s,
                domicilio_fiscal = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        cursor.execute(query, (nombre, telefono, rfc, razon_social, domicilio_fiscal, usuario_id))
        conn.commit()

        # Actualizar sesión
        session['nombre'] = nombre

        flash('Perfil actualizado exitosamente.', 'success')
        return redirect(url_for('portal_perfil'))

    except Exception as e:
        app.logger.error(f"Error actualizando perfil: {e}")
        flash('Error al actualizar perfil.', 'error')
        return redirect(url_for('portal_perfil'))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================================
# API ENDPOINTS (para AJAX)
# ============================================================================

@app.route('/api/portal/facturas/stats')
@login_required
def api_facturas_stats():
    """Estadísticas de facturas para gráficos"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión'}), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Stats por mes
        query = """
            SELECT
                DATE_TRUNC('month', created_at) as mes,
                COUNT(*) as total,
                SUM(amount) as monto_total,
                COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as pagadas
            FROM facturas
            WHERE usuario_id = %s
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY mes DESC
            LIMIT 12
        """
        cursor.execute(query, (usuario_id,))
        stats = cursor.fetchall()

        return jsonify({
            'success': True,
            'data': [dict(row) for row in stats]
        })

    except Exception as e:
        app.logger.error(f"Error obteniendo stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/api/portal/notificaciones/count')
@login_required
def api_notificaciones_count():
    """Contador de notificaciones no leídas (para polling)"""
    usuario_id = session['usuario_id']

    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Error de conexión'}), 500

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        query = """
            SELECT COUNT(*) as count
            FROM notificaciones
            WHERE usuario_id = %s AND leida = FALSE
        """
        cursor.execute(query, (usuario_id,))
        result = cursor.fetchone()

        return jsonify({
            'success': True,
            'count': result['count']
        })

    except Exception as e:
        app.logger.error(f"Error obteniendo count: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ============================================================================
# NOTAS DE IMPLEMENTACIÓN
# ============================================================================

"""
PARA AGREGAR ESTE MÓDULO A APP.PY:

1. Al inicio de app.py, después de las importaciones existentes, agregar:

   from portal_usuarios import *

2. O copiar y pegar todo este código al final de app.py (antes del if __name__ == '__main__')

3. Crear las siguientes plantillas en templates/portal/:
   - login.html
   - dashboard.html
   - factura_detalle.html
   - notificaciones.html
   - perfil.html

4. Asegurarse de que SECRET_KEY esté configurado en Config

5. Ejecutar el SQL de database_schema.sql para crear las tablas

6. Configurar en n8n la variable de entorno PORTAL_URL con la URL del portal
   (por ejemplo: http://tu-dominio.com/portal)

7. Actualizar el payload del portal Flask para incluir receiver_id:

   En app.py, función procesar_factura(), agregar a payload:

   'receiver_id': 'VALOR_DEL_RECEIVER_ID',  # Obtener de orden_ml
   'shipment_id': 'VALOR_DEL_SHIPMENT_ID',   # Opcional
   'nombre': 'NOMBRE_DEL_CLIENTE',           # Opcional

8. Para obtener receiver_id, modificar buscar_pedido() para incluir:

   query = \"\"\"
       SELECT order_id, paid_amount, buyer_nickname, currency_id,
              receiver_id, shipment_id
       FROM public.orden_ml
       WHERE order_id = %s OR pack_id = %s
   \"\"\"

SEGURIDAD:
- El receiver_id se usa como contraseña (simple pero funcional)
- Para mayor seguridad, considera hashear la contraseña
- Implementar rate limiting para evitar ataques de fuerza bruta
- Usar HTTPS en producción
- Configurar CORS si es necesario
"""
