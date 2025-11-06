-- ============================================================================
-- TABLA PARA TRACKING DE SOLICITUDES EN TIEMPO REAL
-- Autor: Portal de Facturación
-- Descripción: Tabla para que n8n actualice el estado de cada solicitud
-- ============================================================================

-- Eliminar tabla si existe (solo para desarrollo, comentar en producción)
-- DROP TABLE IF EXISTS solicitudes_status CASCADE;

-- Crear tabla principal
CREATE TABLE IF NOT EXISTS solicitudes_status (
    id SERIAL PRIMARY KEY,

    -- Identificador único de la solicitud
    order_id VARCHAR(100) NOT NULL UNIQUE,  -- order_id del pedido

    -- Estado actual del proceso
    estado VARCHAR(50) NOT NULL DEFAULT 'iniciado',
    mensaje TEXT,  -- Mensaje descriptivo para mostrar al usuario
    progreso INT DEFAULT 0 CHECK (progreso >= 0 AND progreso <= 100),  -- 0 a 100

    -- Datos adicionales (JSON flexible para cualquier info extra)
    detalles JSONB DEFAULT '{}'::jsonb,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================================================================
-- ÍNDICES PARA BÚSQUEDA RÁPIDA
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_status_order_id ON solicitudes_status(order_id);
CREATE INDEX IF NOT EXISTS idx_status_estado ON solicitudes_status(estado);
CREATE INDEX IF NOT EXISTS idx_status_created_at ON solicitudes_status(created_at DESC);

-- ============================================================================
-- TRIGGER PARA AUTO-ACTUALIZAR updated_at
-- ============================================================================

CREATE OR REPLACE FUNCTION update_status_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS trigger_update_status_timestamp ON solicitudes_status;

CREATE TRIGGER trigger_update_status_timestamp
    BEFORE UPDATE ON solicitudes_status
    FOR EACH ROW
    EXECUTE FUNCTION update_status_timestamp();

-- ============================================================================
-- COMENTARIOS PARA DOCUMENTACIÓN
-- ============================================================================

COMMENT ON TABLE solicitudes_status IS 'Tracking en tiempo real de solicitudes de facturación';
COMMENT ON COLUMN solicitudes_status.order_id IS 'ID del pedido (único)';
COMMENT ON COLUMN solicitudes_status.estado IS 'Estado actual: iniciado, validando, buscando_cliente, creando_cliente, procesando_csf, extrayendo_rfc, creando_factura, timbrando, enviando_email, completado, error';
COMMENT ON COLUMN solicitudes_status.mensaje IS 'Mensaje descriptivo para mostrar al usuario';
COMMENT ON COLUMN solicitudes_status.progreso IS 'Porcentaje de completitud (0-100)';
COMMENT ON COLUMN solicitudes_status.detalles IS 'JSON con datos adicionales del proceso';

-- ============================================================================
-- EJEMPLOS DE USO (para n8n)
-- ============================================================================

/*
-- 1️⃣ CREAR REGISTRO INICIAL (al inicio del flujo n8n):
INSERT INTO solicitudes_status (order_id, estado, mensaje, progreso, detalles)
VALUES (
    '{{ $json.order_id }}',
    'iniciado',
    'Solicitud recibida, validando datos...',
    5,
    jsonb_build_object(
        'email', '{{ $json.email }}',
        'timestamp', NOW()
    )
)
ON CONFLICT (order_id) DO UPDATE SET
    estado = 'iniciado',
    mensaje = 'Solicitud recibida, validando datos...',
    progreso = 5,
    updated_at = NOW();


-- 2️⃣ ACTUALIZAR ESTADO (en cada paso del flujo):
UPDATE solicitudes_status
SET
    estado = 'validando',
    mensaje = 'Validando información del pedido...',
    progreso = 15,
    detalles = detalles || jsonb_build_object('paso', 'validacion_completada')
WHERE order_id = '{{ $json.order_id }}';


-- 3️⃣ MARCAR COMO COMPLETADO:
UPDATE solicitudes_status
SET
    estado = 'completado',
    mensaje = '¡Factura generada exitosamente!',
    progreso = 100,
    detalles = detalles || jsonb_build_object(
        'invoice_id', '{{ $json.invoice_id }}',
        'completado_at', NOW()
    )
WHERE order_id = '{{ $json.order_id }}';


-- 4️⃣ MARCAR ERROR:
UPDATE solicitudes_status
SET
    estado = 'error',
    mensaje = 'Error: {{ $json.error_message }}',
    progreso = 0,
    detalles = detalles || jsonb_build_object(
        'error', '{{ $json.error_message }}',
        'error_at', NOW()
    )
WHERE order_id = '{{ $json.order_id }}';


-- 5️⃣ CONSULTAR ESTADO (desde Flask):
SELECT * FROM solicitudes_status WHERE order_id = 'ORDER123' ORDER BY updated_at DESC LIMIT 1;
*/

-- ============================================================================
-- DATOS DE PRUEBA (opcional, comentar en producción)
-- ============================================================================

/*
INSERT INTO solicitudes_status (order_id, estado, mensaje, progreso, detalles) VALUES
('TEST-001', 'validando', 'Validando información del pedido...', 15, '{"email": "test@test.com"}'::jsonb),
('TEST-002', 'creando_factura', 'Creando factura en Odoo...', 65, '{"cliente_id": 123}'::jsonb),
('TEST-003', 'completado', '¡Factura generada exitosamente!', 100, '{"invoice_id": "INV/2024/001"}'::jsonb);
*/
