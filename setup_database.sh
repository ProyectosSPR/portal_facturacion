#!/bin/bash

# =====================================================
# Script para crear tablas del portal de facturación
# =====================================================

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                                                               ║"
echo "║   Setup Database - Portal de Facturación Mercado Libre      ║"
echo "║                                                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Configuración de la base de datos
DB_HOST="192.168.80.8"
DB_PORT="30432"
DB_NAME="mercadoLibre"
DB_USER="dml"
DB_PASSWORD="Sergio55"
SQL_FILE="database_schema.sql"

# Verificar que existe el archivo SQL
if [ ! -f "$SQL_FILE" ]; then
    echo "❌ ERROR: No se encuentra el archivo $SQL_FILE"
    echo "   Asegúrate de estar en el directorio /home/dml/portal_facturacion/"
    exit 1
fi

echo "📋 Configuración:"
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo "   SQL File: $SQL_FILE"
echo ""

# Preguntar confirmación
read -p "¿Deseas continuar y crear las tablas? (s/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "❌ Operación cancelada"
    exit 1
fi

echo ""
echo "🚀 Ejecutando SQL..."
echo ""

# Ejecutar SQL
export PGPASSWORD="$DB_PASSWORD"

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

if [ $? -eq 0 ]; then
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                                                               ║"
    echo "║   ✅ TABLAS CREADAS EXITOSAMENTE                             ║"
    echo "║                                                               ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📊 Verificando tablas creadas:"
    echo ""

    # Verificar tablas
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt" | grep -E "usuarios_portal|facturas|sesiones_portal|historial_accesos|notificaciones"

    echo ""
    echo "📝 Próximos pasos:"
    echo "   1. Modificar app.py para incluir receiver_id"
    echo "   2. Crear templates HTML en templates/portal/"
    echo "   3. Probar el workflow con: python3 test_webhook.py"
    echo ""
else
    echo ""
    echo "❌ ERROR al ejecutar el SQL"
    echo "   Revisa los errores arriba"
    echo ""
    exit 1
fi

unset PGPASSWORD
