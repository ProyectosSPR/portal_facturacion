"""
Configuración de la aplicación Portal de Facturación
Usar variables de entorno para datos sensibles en producción
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuración base de la aplicación"""

    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # PostgreSQL - Base de datos de Mercado Libre
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'nombre_db')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'dml')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'password_placeholder')

    # n8n - Orquestador de Workflows
    N8N_WEBHOOK_URL = os.getenv('N8N_WEBHOOK_URL', 'https://your-n8n-instance.com/webhook/facturacion')

    # Portal de Usuarios - URL pública
    PORTAL_URL = os.getenv('PORTAL_URL', 'http://localhost:5000/portal/login')

    # Catálogos SAT (opciones para los selectores)
    CFDI_USAGE_OPTIONS = [
        ('G01', 'Adquisición de mercancías'),
        ('G03', 'Gastos en general'),
        ('P01', 'Por definir'),
        ('S01', 'Sin efectos fiscales'),
    ]

    PAYMENT_METHOD_OPTIONS = [
        ('01', 'Efectivo'),
        ('02', 'Cheque nominativo'),
        ('03', 'Transferencia electrónica de fondos'),
        ('04', 'Tarjeta de crédito'),
        ('28', 'Tarjeta de débito'),
    ]

    @staticmethod
    def get_postgres_connection_string():
        """Retorna el string de conexión para PostgreSQL"""
        return f"host={Config.POSTGRES_HOST} port={Config.POSTGRES_PORT} dbname={Config.POSTGRES_DB} user={Config.POSTGRES_USER} password={Config.POSTGRES_PASSWORD}"
