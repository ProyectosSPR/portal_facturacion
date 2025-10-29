#!/bin/bash
# Script de despliegue para Portal de Facturación en Kubernetes

set -e  # Salir si hay error

echo "========================================="
echo "Portal de Facturación - Despliegue K8s"
echo "========================================="
echo ""

# Verificar que kubectl esté instalado
if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl no está instalado"
    exit 1
fi

# Verificar conexión al cluster
echo "🔍 Verificando conexión al cluster..."
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Error: No se puede conectar al cluster de Kubernetes"
    exit 1
fi
echo "✅ Conectado al cluster"
echo ""

# Mostrar contexto actual
CURRENT_CONTEXT=$(kubectl config current-context)
echo "📍 Contexto actual: $CURRENT_CONTEXT"
echo "📍 Namespace: default"
echo ""

# Confirmar despliegue
read -p "¿Deseas continuar con el despliegue? (s/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "Despliegue cancelado"
    exit 0
fi

# Aplicar manifiestos
echo ""
echo "📦 Aplicando manifiestos..."
echo ""

echo "1/7 - Aplicando ConfigMap..."
kubectl apply -f configmap.yaml

echo "2/7 - Aplicando Secret..."
kubectl apply -f secret.yaml

echo "3/7 - Aplicando PVC..."
kubectl apply -f pvc.yaml

echo "4/7 - Aplicando Deployment..."
kubectl apply -f deployment.yaml

echo "5/7 - Aplicando Service..."
kubectl apply -f service.yaml

echo "6/7 - Aplicando Ingress (opcional)..."
kubectl apply -f ingress.yaml || echo "⚠️  Ingress no aplicado (puede requerir ingress controller)"

echo "7/7 - Aplicando HPA (opcional)..."
kubectl apply -f hpa.yaml || echo "⚠️  HPA no aplicado (puede requerir metrics-server)"

echo ""
echo "✅ Manifiestos aplicados correctamente"
echo ""

# Esperar a que los pods estén listos
echo "⏳ Esperando a que los pods estén listos..."
kubectl wait --for=condition=ready pod -l app=portal-facturacion --timeout=120s || true

echo ""
echo "========================================="
echo "✅ Despliegue completado"
echo "========================================="
echo ""

# Mostrar estado
echo "📊 Estado actual:"
kubectl get pods -l app=portal-facturacion
echo ""
kubectl get service portal-facturacion
echo ""

# Mostrar comandos útiles
echo "========================================="
echo "📝 Comandos útiles:"
echo "========================================="
echo ""
echo "Ver logs:"
echo "  kubectl logs -l app=portal-facturacion -f"
echo ""
echo "Ver estado:"
echo "  kubectl get all -l app=portal-facturacion"
echo ""
echo "Port-forward para acceso local:"
echo "  kubectl port-forward service/portal-facturacion 5000:5000"
echo "  Acceder en: http://localhost:5000"
echo ""
echo "Eliminar todo:"
echo "  kubectl delete -f ."
echo ""
