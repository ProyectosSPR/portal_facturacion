-- =====================================================
-- SCHEMA COMPLETO: Portal de Facturación Mercado Libre
-- Base de datos: mercadoLibre
-- =====================================================

-- =====================================================
-- 1. TABLA: usuarios_portal
-- Usuarios que pueden acceder al portal de facturas
-- =====================================================
CREATE TABLE IF NOT EXISTS usuarios_portal (
    id SERIAL PRIMARY KEY,
    receiver_id VARCHAR(50) UNIQUE NOT NULL,  -- ID del comprador en Mercado Libre (usado como password)
    email VARCHAR(255) UNIQUE NOT NULL,
    nombre VARCHAR(255),
    telefono VARCHAR(20),

    -- Datos adicionales del usuario
    rfc VARCHAR(13),  -- RFC para facturación
    razon_social VARCHAR(255),
    domicilio_fiscal TEXT,

    -- Control de acceso
    activo BOOLEAN DEFAULT TRUE,
    fecha_registro TIMESTAMP DEFAULT NOW(),
    ultimo_acceso TIMESTAMP,
    intentos_fallidos INTEGER DEFAULT 0,
    bloqueado_hasta TIMESTAMP,

    -- Metadatos
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Índices para búsqueda rápida
    CONSTRAINT email_lowercase CHECK (email = LOWER(email))
);

-- Índices para usuarios_portal
CREATE INDEX idx_usuarios_receiver_id ON usuarios_portal(receiver_id);
CREATE INDEX idx_usuarios_email ON usuarios_portal(email);
CREATE INDEX idx_usuarios_activo ON usuarios_portal(activo);

-- =====================================================
-- 2. TABLA: facturas
-- Registro de todas las facturas generadas
-- =====================================================
CREATE TABLE IF NOT EXISTS facturas (
    id SERIAL PRIMARY KEY,

    -- Relación con usuario
    usuario_id INTEGER REFERENCES usuarios_portal(id) ON DELETE CASCADE,
    receiver_id VARCHAR(50) NOT NULL,  -- ID del comprador en Mercado Libre

    -- Datos de Mercado Libre
    order_id VARCHAR(50) UNIQUE NOT NULL,  -- ID del pedido en ML
    shipment_id VARCHAR(50),  -- ID del envío si existe

    -- Datos de la factura en Odoo
    invoice_id INTEGER,  -- ID de la factura en Odoo
    invoice_name VARCHAR(100),  -- Nombre/número de factura (ej: INV/2024/001)

    -- Datos del cliente
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),

    -- Datos de facturación
    amount DECIMAL(10, 2) NOT NULL,
    currency_id VARCHAR(3) DEFAULT 'MXN',
    cfdi_usage VARCHAR(10),  -- Uso de CFDI (G03, etc.)
    payment_method VARCHAR(10),  -- Forma de pago (04, etc.)

    -- Archivos de facturación
    pdf_url TEXT,  -- URL o path del PDF de la factura
    xml_url TEXT,  -- URL o path del XML de la factura
    csf_pdf_url TEXT,  -- URL o path del PDF de CSF (Constancia Situación Fiscal)

    -- Control de estatus
    status VARCHAR(50) DEFAULT 'created',  -- created, sent, paid, cancelled, error

    -- Información de pago
    payment_status VARCHAR(50) DEFAULT 'pending',  -- pending, partial, paid, overdue
    paid_amount DECIMAL(10, 2) DEFAULT 0,
    payment_date DATE,

    -- Observaciones y notas
    observaciones_contabilidad TEXT,  -- Notas del equipo de contabilidad
    notas_internas TEXT,  -- Notas internas (no visibles para cliente)
    notas_cliente TEXT,  -- Notas visibles para el cliente

    -- Tracking de envío de factura
    email_enviado BOOLEAN DEFAULT FALSE,
    email_enviado_fecha TIMESTAMP,

    -- Metadatos
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    -- Datos adicionales del pedido (JSON)
    metadata JSONB,  -- Información adicional del pedido ML

    -- Audit trail
    created_by VARCHAR(100) DEFAULT 'sistema',
    updated_by VARCHAR(100)
);

-- Índices para facturas
CREATE INDEX idx_facturas_order_id ON facturas(order_id);
CREATE INDEX idx_facturas_usuario_id ON facturas(usuario_id);
CREATE INDEX idx_facturas_receiver_id ON facturas(receiver_id);
CREATE INDEX idx_facturas_invoice_id ON facturas(invoice_id);
CREATE INDEX idx_facturas_status ON facturas(status);
CREATE INDEX idx_facturas_payment_status ON facturas(payment_status);
CREATE INDEX idx_facturas_email ON facturas(email);
CREATE INDEX idx_facturas_created_at ON facturas(created_at DESC);

-- =====================================================
-- 3. TABLA: sesiones_portal
-- Control de sesiones activas
-- =====================================================
CREATE TABLE IF NOT EXISTS sesiones_portal (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios_portal(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    fecha_inicio TIMESTAMP DEFAULT NOW(),
    fecha_expiracion TIMESTAMP NOT NULL,
    activa BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_sesiones_usuario_id ON sesiones_portal(usuario_id);
CREATE INDEX idx_sesiones_token ON sesiones_portal(session_token);
CREATE INDEX idx_sesiones_activa ON sesiones_portal(activa);

-- =====================================================
-- 4. TABLA: historial_accesos
-- Log de accesos al portal
-- =====================================================
CREATE TABLE IF NOT EXISTS historial_accesos (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios_portal(id) ON DELETE CASCADE,
    email VARCHAR(255),
    receiver_id VARCHAR(50),
    tipo_evento VARCHAR(50),  -- login_exitoso, login_fallido, logout, cambio_password
    ip_address INET,
    user_agent TEXT,
    exitoso BOOLEAN DEFAULT TRUE,
    mensaje TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_historial_usuario_id ON historial_accesos(usuario_id);
CREATE INDEX idx_historial_created_at ON historial_accesos(created_at DESC);
CREATE INDEX idx_historial_tipo_evento ON historial_accesos(tipo_evento);

-- =====================================================
-- 5. TABLA: notificaciones
-- Notificaciones para usuarios
-- =====================================================
CREATE TABLE IF NOT EXISTS notificaciones (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER REFERENCES usuarios_portal(id) ON DELETE CASCADE,
    factura_id INTEGER REFERENCES facturas(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL,  -- factura_creada, pago_recibido, observacion_agregada
    titulo VARCHAR(255) NOT NULL,
    mensaje TEXT NOT NULL,
    leida BOOLEAN DEFAULT FALSE,
    fecha_leida TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_notificaciones_usuario_id ON notificaciones(usuario_id);
CREATE INDEX idx_notificaciones_leida ON notificaciones(leida);
CREATE INDEX idx_notificaciones_created_at ON notificaciones(created_at DESC);

-- =====================================================
-- 6. FUNCIONES Y TRIGGERS
-- =====================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para usuarios_portal
DROP TRIGGER IF EXISTS update_usuarios_portal_updated_at ON usuarios_portal;
CREATE TRIGGER update_usuarios_portal_updated_at
    BEFORE UPDATE ON usuarios_portal
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger para facturas
DROP TRIGGER IF EXISTS update_facturas_updated_at ON facturas;
CREATE TRIGGER update_facturas_updated_at
    BEFORE UPDATE ON facturas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Función para crear notificación cuando se crea una factura
CREATE OR REPLACE FUNCTION crear_notificacion_factura()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.usuario_id IS NOT NULL THEN
        INSERT INTO notificaciones (usuario_id, factura_id, tipo, titulo, mensaje)
        VALUES (
            NEW.usuario_id,
            NEW.id,
            'factura_creada',
            'Factura creada exitosamente',
            'Su factura para el pedido ' || NEW.order_id || ' ha sido creada. Monto: $' || NEW.amount || ' ' || NEW.currency_id
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para crear notificación al crear factura
DROP TRIGGER IF EXISTS trigger_notificacion_factura ON facturas;
CREATE TRIGGER trigger_notificacion_factura
    AFTER INSERT ON facturas
    FOR EACH ROW
    EXECUTE FUNCTION crear_notificacion_factura();

-- =====================================================
-- 7. VISTAS ÚTILES
-- =====================================================

-- Vista para el dashboard del usuario
CREATE OR REPLACE VIEW vista_facturas_usuario AS
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
    f.updated_at,
    u.receiver_id,
    u.email,
    u.nombre
FROM facturas f
INNER JOIN usuarios_portal u ON f.usuario_id = u.id
WHERE u.activo = TRUE;

-- Vista para estadísticas de facturación
CREATE OR REPLACE VIEW vista_estadisticas_facturas AS
SELECT
    DATE_TRUNC('month', created_at) as mes,
    COUNT(*) as total_facturas,
    SUM(amount) as monto_total,
    COUNT(CASE WHEN payment_status = 'paid' THEN 1 END) as facturas_pagadas,
    SUM(CASE WHEN payment_status = 'paid' THEN paid_amount ELSE 0 END) as monto_pagado,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as facturas_error
FROM facturas
GROUP BY DATE_TRUNC('month', created_at)
ORDER BY mes DESC;

-- =====================================================
-- 8. COMENTARIOS EN TABLAS
-- =====================================================

COMMENT ON TABLE usuarios_portal IS 'Usuarios que pueden acceder al portal de facturas';
COMMENT ON TABLE facturas IS 'Registro de todas las facturas generadas para pedidos de Mercado Libre';
COMMENT ON TABLE sesiones_portal IS 'Control de sesiones activas de usuarios';
COMMENT ON TABLE historial_accesos IS 'Log de todos los accesos al portal';
COMMENT ON TABLE notificaciones IS 'Notificaciones para usuarios del portal';

COMMENT ON COLUMN usuarios_portal.receiver_id IS 'ID del comprador en Mercado Libre - usado como contraseña';
COMMENT ON COLUMN facturas.order_id IS 'ID único del pedido en Mercado Libre';
COMMENT ON COLUMN facturas.invoice_id IS 'ID de la factura en Odoo';
COMMENT ON COLUMN facturas.status IS 'Estado: created, sent, paid, cancelled, error';
COMMENT ON COLUMN facturas.payment_status IS 'Estado de pago: pending, partial, paid, overdue';

-- =====================================================
-- 9. PERMISOS (AJUSTAR SEGÚN TU CONFIGURACIÓN)
-- =====================================================

-- Asegurar que el usuario 'dml' tenga todos los permisos
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dml;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dml;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dml;

-- =====================================================
-- FIN DEL SCHEMA
-- =====================================================
