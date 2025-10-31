#!/usr/bin/env python3
"""
Script de prueba para el webhook de facturación de Mercado Libre
Ejecutar: python3 test_webhook.py
"""

import requests
import json
import base64
from datetime import datetime

# URL del webhook
WEBHOOK_URL = "https://aut.automateai.com.mx/webhook/a86064e4-d5ef-4abe-85cd-be0362757f88"

# PDF de prueba en base64 (un PDF mínimo válido)
PDF_BASE64 = """JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9UeXBlIC9QYWdlCi9QYXJlbnQgMSAwIFIKL01lZGlhQm94IFsw
IDAgNjEyIDc5Ml0KL0NvbnRlbnRzIDQgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwvRmlsdGVyIC9GbGF0ZURl
Y29kZQovTGVuZ3RoIDQ0Pj4Kc3RyZWFtCniCy1ZKSyxJTVFISs2rLC7OT1HILSjJzM9TSMsvUgCCnFSF4pKi
zLx0hZzU5BIFheT8PAUFXQUFCJvLFgCjIREKZW5kc3RyZWFtCmVuZG9iagoxIDAgb2JqCjw8L1R5cGUgL1Bh
Z2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDE+PgplbmRvYmoKNSAwIG9iago8PC9UeXBlIC9Gb250Ci9CYXNl
Rm9udCAvSGVsdmV0aWNhCi9TdWJ0eXBlIC9UeXBlMT4+CmVuZG9iago2IDAgb2JqCjw8L1R5cGUgL0ZvbnQK
L0Jhc2VGb250IC9IZWx2ZXRpY2EtQm9sZAovU3VidHlwZSAvVHlwZTE+PgplbmRvYmoKMiAwIG9iago8PC9U
eXBlIC9DYXRhbG9nCi9QYWdlcyAxIDAgUj4+CmVuZG9iago3IDAgb2JqCjw8L1R5cGUgL0ZvbnRSZXNvdXJj
ZXMKRm9udCA8PC9GMSA1IDAgUj4+Pj4KZW5kb2JqCnhyZWYKMCA4CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAw
MDAwMDE4OCAwMDAwMCBuIAowMDAwMDAwMzM3IDAwMDAwIG4gCjAwMDAwMDAwMDkgMDAwMDAgbiAKMDAwMDAw
MDA4NyAwMDAwMCBuIAowMDAwMDAwMjQ1IDAwMDAwIG4gCjAwMDAwMDAzMTkgMDAwMDAgbiAKMDAwMDAwMDM4
NiAwMDAwMCBuIAp0cmFpbGVyCjw8L1NpemUgOAovUm9vdCAyIDAgUj4+CnN0YXJ0eHJlZgo0MzUKJSVFT0YK"""

# Eliminar saltos de línea del base64
PDF_BASE64 = PDF_BASE64.replace('\n', '').replace(' ', '')


def crear_payload_prueba(order_id_suffix="TEST", receiver_id="123456789"):
    """
    Crea un payload de prueba para el webhook
    """
    timestamp = datetime.now().isoformat()

    payload = {
        "order_id": f"{order_id_suffix}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "paid_amount": 1844.25,
        "currency_id": "MXN",
        "email": "test@example.com",
        "phone": "4776642162",
        "cfdi_usage": "G03",
        "payment_method": "04",
        "monto_pagado": 1844.25,

        # IMPORTANTE: Datos del comprador
        "receiver_id": receiver_id,
        "nombre": f"Cliente Prueba {receiver_id}",
        "shipment_id": f"SHIP_{datetime.now().strftime('%Y%m%d%H%M%S')}",

        "csf_pdf": {
            "filename": "test_csf.pdf",
            "content": PDF_BASE64,
            "mime_type": "application/pdf"
        },
        "timestamp": timestamp,
        "source": "portal_flask_test"
    }

    return payload


def enviar_webhook(payload, verbose=True):
    """
    Envía el payload al webhook y retorna la respuesta
    """
    if verbose:
        print(f"\n{'='*60}")
        print(f"Enviando prueba al webhook...")
        print(f"URL: {WEBHOOK_URL}")
        print(f"Order ID: {payload['order_id']}")
        print(f"Receiver ID: {payload['receiver_id']}")
        print(f"Email: {payload['email']}")
        print(f"Monto: ${payload['paid_amount']} {payload['currency_id']}")
        print(f"{'='*60}\n")

    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=60
        )

        if verbose:
            print(f"Status Code: {response.status_code}")
            print(f"\nRespuesta:")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))

        return response

    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar el webhook: {e}")
        return None


def main():
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║   Script de Prueba - Webhook Facturación Mercado Libre      ║
║   Con Sistema de Usuarios                                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
    """)

    # Pedir datos al usuario
    print("Configuración de prueba:\n")

    email = input("Email (Enter para test@example.com): ").strip() or "test@example.com"
    receiver_id = input("Receiver ID (Enter para 123456789): ").strip() or "123456789"
    phone = input("Teléfono (Enter para 4776642162): ").strip() or "4776642162"
    amount = input("Monto (Enter para 1844.25): ").strip() or "1844.25"

    # Crear payload
    payload = crear_payload_prueba(receiver_id=receiver_id)
    payload['email'] = email
    payload['phone'] = phone
    payload['paid_amount'] = float(amount)
    payload['monto_pagado'] = float(amount)

    # Enviar
    response = enviar_webhook(payload)

    if response and response.status_code == 200:
        data = response.json()

        print("\n" + "="*60)
        print("RESULTADO:")
        print("="*60)

        if data.get('success'):
            print("✅ ÉXITO - Factura creada")
            print(f"\n📋 Detalles:")
            print(f"  Invoice ID: {data.get('invoice_id')}")
            print(f"  Order ID: {data.get('order_id')}")

            if 'portal_access' in data:
                print(f"\n🔐 Acceso al Portal:")
                print(f"  URL: {data['portal_access'].get('url')}")
                print(f"  Email: {data['portal_access'].get('email')}")
                print(f"  Password: {data['portal_access'].get('password')}")
                print(f"\n  {data['portal_access'].get('mensaje')}")
        else:
            print("❌ ERROR")
            print(f"  Mensaje: {data.get('message')}")
            if 'invoice_id' in data:
                print(f"  Invoice ID existente: {data.get('invoice_id')}")

    print("\n" + "="*60)


if __name__ == "__main__":
    main()
