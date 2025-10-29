#!/bin/bash
# Script para eliminar Portal de Facturación de Kubernetes

set -e

echo "========================================="
echo "Portal de Facturación - Eliminar K8s"
echo "========================================="
echo ""

# Verificar kubectl
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl no está instalado"
    exit 1
fi

# Mostrar recursos actuales
echo "📊 Recursos actuales:"
kubectl get all -l app=portal-facturacion
echo ""

# Confirmar eliminación
echo "⚠️  ADVERTENCIA: Esto eliminará todos los recursos del Portal de Facturación"
read -p "¿Estás seguro? (s/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Operación cancelada"
    exit 0
fi

# Eliminar recursos
echo ""
echo "🗑️  Eliminando recursos..."
echo ""

kubectl delete -f hpa.yaml 2>/dev/null || echo "HPA no encontrado"
kubectl delete -f ingress.yaml 2>/dev/null || echo "Ingress no encontrado"
kubectl delete -f service.yaml 2>/dev/null || echo "Service no encontrado"
kubectl delete -f deployment.yaml 2>/dev/null || echo "Deployment no encontrado"

# Preguntar si eliminar PVC (datos persistentes)
echo ""
read -p "¿Eliminar también el PVC (volumen de uploads)? Esto borrará los archivos (s/n): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Ss]$ ]]; then
    kubectl delete -f pvc.yaml 2>/dev/null || echo "PVC no encontrado"
fi

kubectl delete -f secret.yaml 2>/dev/null || echo "Secret no encontrado"
kubectl delete -f configmap.yaml 2>/dev/null || echo "ConfigMap no encontrado"

echo ""
echo "✅ Recursos eliminados"
echo ""

# Verificar que todo se eliminó
echo "📊 Recursos restantes:"
kubectl get all -l app=portal-facturacion || echo "No hay recursos"
echo ""
