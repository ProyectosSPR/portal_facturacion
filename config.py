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

    # Catálogos SAT (opciones para los selectores)
    CFDI_USAGE_OPTIONS = [
        ('G01', 'Adquisición de mercancías'),
        ('G02', 'Devoluciones, descuentos o bonificaciones'),
        ('G03', 'Gastos en general'),
        ('I01', 'Construcciones'),
        ('I02', 'Mobilario y equipo de oficina por inversiones'),
        ('I03', 'Equipo de transporte'),
        ('I04', 'Equipo de cómputo y accesorios'),
        ('I05', 'Dados, troqueles, moldes, matrices y herramental'),
        ('I06', 'Comunicaciones telefónicas'),
        ('I07', 'Comunicaciones satelitales'),
        ('I08', 'Otra maquinaria y equipo'),
        ('D01', 'Honorarios médicos, dentales y gastos hospitalarios'),
        ('D02', 'Gastos médicos por incapacidad o discapacidad'),
        ('D03', 'Gastos funerales'),
        ('D04', 'Donativos'),
        ('D05', 'Intereses reales efectivamente pagados por créditos hipotecarios'),
        ('D06', 'Aportaciones voluntarias al SAR'),
        ('D07', 'Primas por seguros de gastos médicos'),
        ('D08', 'Gastos de transportación escolar obligatoria'),
        ('D09', 'Depósitos en cuentas para el ahorro'),
        ('D10', 'Pagos por servicios educativos'),
        ('P01', 'Por definir'),
        ('S01', 'Sin efectos fiscales'),
        ('CP01', 'Pagos'),
        ('CN01', 'Nómina'),
    ]

    PAYMENT_METHOD_OPTIONS = [
        ('01', 'Efectivo'),
        ('02', 'Cheque nominativo'),
        ('03', 'Transferencia electrónica de fondos'),
        ('04', 'Tarjeta de crédito'),
        ('05', 'Monedero electrónico'),
        ('06', 'Dinero electrónico'),
        ('08', 'Vales de despensa'),
        ('12', 'Dación en pago'),
        ('13', 'Pago por subrogación'),
        ('14', 'Pago por consignación'),
        ('15', 'Condonación'),
        ('17', 'Compensación'),
        ('23', 'Novación'),
        ('24', 'Confusión'),
        ('25', 'Remisión de deuda'),
        ('26', 'Prescripción o caducidad'),
        ('27', 'A satisfacción del acreedor'),
        ('28', 'Tarjeta de débito'),
        ('29', 'Tarjeta de servicios'),
        ('30', 'Aplicación de anticipos'),
        ('31', 'Intermediario pagos'),
        ('99', 'Por definir'),
    ]

    @staticmethod
    def get_postgres_connection_string():
        """Retorna el string de conexión para PostgreSQL"""
        return f"host={Config.POSTGRES_HOST} port={Config.POSTGRES_PORT} dbname={Config.POSTGRES_DB} user={Config.POSTGRES_USER} password={Config.POSTGRES_PASSWORD}"
