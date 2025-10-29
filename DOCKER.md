# Guía de Docker - Portal de Facturación

## 🐳 Comandos Básicos

### Construir la imagen

```bash
docker build -t portal-facturacion:latest .
```

### Construir con docker-compose

```bash
docker-compose build
```

### Ejecutar el contenedor

**Opción 1: Con docker-compose (recomendado)**
```bash
docker-compose up
```

**En background:**
```bash
docker-compose up -d
```

**Opción 2: Con docker run directo**
```bash
docker run -d \
  --name portal-facturacion \
  -p 5000:5000 \
  --env-file .env \
  -v $(pwd)/uploads:/app/uploads \
  --restart unless-stopped \
  portal-facturacion:latest
```

## 📋 Gestión del Contenedor

### Ver logs
```bash
docker-compose logs -f
```

O con docker directo:
```bash
docker logs -f portal-facturacion
```

### Ver logs de las últimas 100 líneas
```bash
docker-compose logs --tail=100
```

### Detener el contenedor
```bash
docker-compose down
```

### Reiniciar el contenedor
```bash
docker-compose restart
```

### Ver estado
```bash
docker-compose ps
```

### Ejecutar comandos dentro del contenedor
```bash
docker-compose exec portal-facturacion bash
```

O con docker directo:
```bash
docker exec -it portal-facturacion bash
```

## 🔄 Actualización de la Aplicación

Cuando hagas cambios al código:

```bash
# 1. Detener el contenedor
docker-compose down

# 2. Reconstruir la imagen
docker-compose build

# 3. Iniciar de nuevo
docker-compose up -d
```

O todo en uno:
```bash
docker-compose up -d --build
```

## 🧹 Limpieza

### Eliminar contenedor
```bash
docker-compose down
```

### Eliminar contenedor y volúmenes
```bash
docker-compose down -v
```

### Eliminar imagen
```bash
docker rmi portal-facturacion:latest
```

### Limpiar todo Docker (contenedores, imágenes, volúmenes no usados)
```bash
docker system prune -a --volumes
```

## 🔍 Debugging

### Ver variables de entorno dentro del contenedor
```bash
docker-compose exec portal-facturacion env
```

### Ver procesos corriendo dentro del contenedor
```bash
docker-compose exec portal-facturacion ps aux
```

### Verificar salud del contenedor
```bash
docker inspect --format='{{json .State.Health}}' portal-facturacion | jq
```

### Probar conectividad desde dentro del contenedor
```bash
docker-compose exec portal-facturacion curl http://localhost:5000/
```

## 🌐 Acceso a la Aplicación

Una vez corriendo el contenedor, accede en:
- **Local**: http://localhost:5000
- **Red**: http://[IP-DEL-SERVIDOR]:5000

## 🚀 Producción

### Ejecutar con recursos limitados
```bash
docker run -d \
  --name portal-facturacion \
  -p 5000:5000 \
  --env-file .env \
  --cpus="2" \
  --memory="1g" \
  --restart unless-stopped \
  portal-facturacion:latest
```

### Con nginx como reverse proxy
Ver sección de nginx en README.md

## 📊 Monitoreo

### Ver uso de recursos
```bash
docker stats portal-facturacion
```

### Ver uso de disco
```bash
docker system df
```

## 🔐 Seguridad

### Escanear la imagen por vulnerabilidades (Docker Scout)
```bash
docker scout cves portal-facturacion:latest
```

### O con Trivy
```bash
trivy image portal-facturacion:latest
```

## 📦 Export/Import de Imagen

### Exportar imagen a archivo
```bash
docker save -o portal-facturacion.tar portal-facturacion:latest
```

### Importar imagen desde archivo
```bash
docker load -i portal-facturacion.tar
```

## 🔄 Docker Compose - Comandos Avanzados

### Ver configuración final
```bash
docker-compose config
```

### Forzar recreación de contenedores
```bash
docker-compose up -d --force-recreate
```

### Build sin cache
```bash
docker-compose build --no-cache
```

### Ver solo errores en logs
```bash
docker-compose logs | grep ERROR
```

## 💡 Tips

1. **Desarrollo**: Si estás desarrollando, puedes montar el código como volumen para hot-reload:
   ```yaml
   volumes:
     - .:/app
   ```
   Y cambiar el CMD a:
   ```dockerfile
   CMD ["python", "app.py"]
   ```

2. **Producción**: Usa gunicorn (como está configurado por defecto) con múltiples workers.

3. **Variables de entorno**: Nunca subas el archivo `.env` a git. Usa `.env.example` como plantilla.

4. **Logs**: En producción, considera usar un sistema de logging centralizado (ELK, Loki, etc.).

5. **Backups**: Si usas volúmenes, asegúrate de hacer backup regularmente:
   ```bash
   docker run --rm -v portal-facturacion_uploads-data:/data -v $(pwd):/backup ubuntu tar czf /backup/uploads-backup.tar.gz /data
   ```

## 🐛 Troubleshooting

### El contenedor no inicia
```bash
# Ver logs completos
docker-compose logs

# Verificar que el puerto no esté ocupado
sudo netstat -tulpn | grep 5000

# Verificar el .env
cat .env
```

### Error de permisos con uploads
```bash
# Dentro del contenedor
docker-compose exec portal-facturacion ls -la /app/uploads
docker-compose exec portal-facturacion chmod 777 /app/uploads
```

### Error de conexión a Postgres
```bash
# Verificar conectividad desde el contenedor
docker-compose exec portal-facturacion ping [POSTGRES_HOST]
docker-compose exec portal-facturacion nc -zv [POSTGRES_HOST] 5432
```

### Contenedor se detiene inmediatamente
```bash
# Ver logs de error
docker logs portal-facturacion

# Ejecutar en modo interactivo para debug
docker run -it --rm portal-facturacion:latest bash
```
