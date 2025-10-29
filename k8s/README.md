# Manifiestos de Kubernetes - Portal de Facturación

Esta carpeta contiene todos los manifiestos necesarios para desplegar el Portal de Facturación en Kubernetes.

## 📋 Arquitectura en Kubernetes

```
Internet
    ↓
  Ingress (opcional)
    ↓
  Service (ClusterIP)
    ↓
  Deployment (2+ Pods)
    ↓
  ConfigMap + Secret (Variables de entorno)
    ↓
  PVC (Volumen para uploads)
```

## 📦 Archivos Incluidos

| Archivo | Descripción |
|---------|-------------|
| `configmap.yaml` | Variables de entorno no sensibles |
| `secret.yaml` | Credenciales y datos sensibles |
| `pvc.yaml` | Volumen persistente para uploads |
| `deployment.yaml` | Despliegue de la aplicación (2 réplicas) |
| `service.yaml` | Servicio ClusterIP para exponer los pods |
| `ingress.yaml` | Ingress para acceso externo (opcional) |
| `hpa.yaml` | Autoescalado horizontal (opcional) |
| `kustomization.yaml` | Configuración de Kustomize |

## 🚀 Despliegue

### Opción 1: Con kubectl (aplicar uno por uno)

```bash
# 1. Aplicar ConfigMap y Secret primero
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml

# 2. Crear PVC
kubectl apply -f pvc.yaml

# 3. Crear Deployment
kubectl apply -f deployment.yaml

# 4. Crear Service
kubectl apply -f service.yaml

# 5. (Opcional) Crear Ingress
kubectl apply -f ingress.yaml

# 6. (Opcional) Crear HPA
kubectl apply -f hpa.yaml
```

### Opción 2: Con kubectl (todo a la vez)

```bash
kubectl apply -f .
```

### Opción 3: Con Kustomize (Recomendado)

```bash
# Desde el directorio k8s/
kubectl apply -k .

# O desde el directorio raíz
kubectl apply -k k8s/
```

## 🔍 Verificación del Despliegue

### Ver todos los recursos
```bash
kubectl get all -l app=portal-facturacion
```

### Ver pods
```bash
kubectl get pods -l app=portal-facturacion
```

### Ver logs
```bash
# Todos los pods
kubectl logs -l app=portal-facturacion -f

# Un pod específico
kubectl logs <pod-name> -f
```

### Ver estado del deployment
```bash
kubectl describe deployment portal-facturacion
```

### Ver estado del service
```bash
kubectl describe service portal-facturacion
```

### Ver PVC
```bash
kubectl get pvc portal-facturacion-uploads
```

## 🔐 Configuración de Secrets

### Método 1: Editar el archivo secret.yaml

Edita `secret.yaml` y cambia los valores en `stringData`:

```yaml
stringData:
  SECRET_KEY: "tu-clave-secreta-aqui"
  POSTGRES_PASSWORD: "tu-password-postgres"
  ODOO_PASSWORD: "tu-password-odoo"
```

### Método 2: Crear secret desde la línea de comandos

```bash
kubectl create secret generic portal-facturacion-secret \
  --from-literal=SECRET_KEY="tu-secret-key" \
  --from-literal=POSTGRES_PASSWORD="tu-password" \
  --from-literal=ODOO_PASSWORD="tu-password" \
  --namespace=default
```

### Método 3: Crear secret desde archivo .env

```bash
kubectl create secret generic portal-facturacion-secret \
  --from-env-file=../.env \
  --namespace=default
```

## 🌐 Acceso a la Aplicación

### Dentro del cluster (Service ClusterIP)
```bash
# Port-forward para acceso local
kubectl port-forward service/portal-facturacion 5000:5000

# Acceder en: http://localhost:5000
```

### Con NodePort (cambiar tipo de Service)

Edita `service.yaml`:
```yaml
spec:
  type: NodePort  # Cambiar de ClusterIP a NodePort
```

Luego:
```bash
kubectl apply -f service.yaml
kubectl get service portal-facturacion
# Acceder en: http://<NODE-IP>:<NODE-PORT>
```

### Con LoadBalancer (en cloud)

Edita `service.yaml`:
```yaml
spec:
  type: LoadBalancer  # Cambiar de ClusterIP a LoadBalancer
```

Luego:
```bash
kubectl apply -f service.yaml
kubectl get service portal-facturacion
# Espera a que se asigne una IP externa
# Acceder en: http://<EXTERNAL-IP>:5000
```

### Con Ingress (recomendado para producción)

1. Asegúrate de tener un Ingress Controller instalado (nginx, traefik, etc.)
2. Edita `ingress.yaml` y configura tu dominio:
   ```yaml
   spec:
     rules:
     - host: facturacion.tudominio.com
   ```
3. Aplica el Ingress:
   ```bash
   kubectl apply -f ingress.yaml
   ```
4. Configura tu DNS para apuntar a la IP del Ingress Controller

## 📊 Monitoreo

### Ver métricas de pods
```bash
kubectl top pods -l app=portal-facturacion
```

### Ver eventos
```bash
kubectl get events --sort-by=.metadata.creationTimestamp
```

### Ver estado del HPA (si está habilitado)
```bash
kubectl get hpa portal-facturacion
kubectl describe hpa portal-facturacion
```

## 🔄 Actualización de la Aplicación

### Actualizar imagen

```bash
# 1. Build nueva imagen
docker build -t portal-facturacion:v2 .

# 2. Push a registry (si usas uno)
docker tag portal-facturacion:v2 tu-registry/portal-facturacion:v2
docker push tu-registry/portal-facturacion:v2

# 3. Actualizar deployment
kubectl set image deployment/portal-facturacion \
  flask-app=tu-registry/portal-facturacion:v2

# O editar kustomization.yaml y aplicar
kubectl apply -k .
```

### Rolling update
```bash
# Ver estado del rollout
kubectl rollout status deployment/portal-facturacion

# Ver historial
kubectl rollout history deployment/portal-facturacion

# Rollback a versión anterior
kubectl rollout undo deployment/portal-facturacion

# Rollback a versión específica
kubectl rollout undo deployment/portal-facturacion --to-revision=2
```

## 🧹 Limpieza

### Eliminar todos los recursos

```bash
# Con kubectl
kubectl delete -f .

# Con kustomize
kubectl delete -k .

# O individualmente
kubectl delete deployment portal-facturacion
kubectl delete service portal-facturacion
kubectl delete configmap portal-facturacion-config
kubectl delete secret portal-facturacion-secret
kubectl delete pvc portal-facturacion-uploads
```

## 🐛 Troubleshooting

### Pods no inician
```bash
# Ver logs del pod
kubectl logs <pod-name>

# Ver eventos del pod
kubectl describe pod <pod-name>

# Ver estado del deployment
kubectl describe deployment portal-facturacion
```

### Error de ImagePullBackOff
```bash
# La imagen no está disponible en el nodo
# Opciones:
# 1. Push imagen a un registry
# 2. Cambiar imagePullPolicy a IfNotPresent
# 3. Usar minikube/kind y cargar imagen local
```

### Problemas de conectividad con Postgres
```bash
# Verificar desde el pod
kubectl exec -it <pod-name> -- bash
ping 10.107.55.29
nc -zv 10.107.55.29 5432

# Verificar variables de entorno
kubectl exec <pod-name> -- env | grep POSTGRES
```

### Secret no se aplica
```bash
# Ver el secret
kubectl get secret portal-facturacion-secret -o yaml

# Verificar que el deployment lo referencia
kubectl describe deployment portal-facturacion | grep -A5 "Environment"
```

### PVC no se monta
```bash
# Ver estado del PVC
kubectl describe pvc portal-facturacion-uploads

# Ver si el pod tiene el volumen
kubectl describe pod <pod-name> | grep -A10 "Volumes"
```

## 🔧 Configuración Avanzada

### Usar un Registry privado

1. Crear secret para Docker registry:
```bash
kubectl create secret docker-registry regcred \
  --docker-server=<registry-url> \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email>
```

2. Agregar al deployment:
```yaml
spec:
  template:
    spec:
      imagePullSecrets:
      - name: regcred
```

### Habilitar SSL con cert-manager

1. Instalar cert-manager
2. Crear ClusterIssuer para Let's Encrypt
3. Agregar anotaciones al Ingress:
```yaml
metadata:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
  - hosts:
    - facturacion.tudominio.com
    secretName: portal-facturacion-tls
```

### Configurar NetworkPolicy (seguridad)

Crear archivo `networkpolicy.yaml`:
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: portal-facturacion-netpol
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: portal-facturacion
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector: {}
    ports:
    - protocol: TCP
      port: 5000
  egress:
  - to:
    - podSelector: {}
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 5432  # Postgres
    - protocol: TCP
      port: 5678  # n8n
```

## 📝 Notas

- **Namespace**: Todos los recursos están en `default` para estar junto con tu Postgres
- **Réplicas**: Por defecto 2 réplicas para alta disponibilidad
- **HPA**: El autoescalado está configurado para escalar hasta 10 réplicas
- **Recursos**: Ajusta los límites de CPU/memoria según tu cluster
- **Imagen**: La imagen debe estar disponible en todos los nodos o en un registry

## 🔗 Referencias

- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Kustomize](https://kustomize.io/)
- [kubectl Cheat Sheet](https://kubernetes.io/docs/reference/kubectl/cheatsheet/)
