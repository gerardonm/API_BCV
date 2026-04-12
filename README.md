# 🏦 API del Banco Central de Venezuela (BCV)

Microservicios de API REST que extraen y exponen datos financieros clave en tiempo real del sitio web oficial del [Banco Central de Venezuela (BCV)](https://www.bcv.org.ve/).

## 📋 Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/tasa-usd` | Tasa de cambio USD y fecha de vigencia |
| `GET` | `/api/v1/indice-inversion` | Índice de Inversión más reciente |
| `GET` | `/api/v1/health` | Health check del servicio |
| `GET` | `/api/docs` | Documentación Swagger UI interactiva |

## 🚀 Instalación y Ejecución

### Requisitos Previos
- Python 3.10+
- pip

### Pasos

```bash
# 1. Navegar al directorio del proyecto
cd API_BCV

# 2. Crear un entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar el servidor
python app.py
```

El servidor estará disponible en **http://localhost:5000**.

## 📖 Uso

### Tasa de Cambio USD

```bash
curl http://localhost:5000/api/v1/tasa-usd
```

**Respuesta:**
```json
{
  "tasa_usd": "477,14880000",
  "fecha_valor": "2026-04-13"
}
```

### Índice de Inversión

```bash
curl http://localhost:5000/api/v1/indice-inversion
```

**Respuesta:**
```json
{
  "fecha_indice": "2026-04-10",
  "tasa_indice_nueva_expresion": "2,32926182"
}
```

### Health Check

```bash
curl http://localhost:5000/api/v1/health
```

**Respuesta:**
```json
{
  "status": "ok",
  "service": "BCV API",
  "version": "1.0.0",
  "timestamp": "2026-04-11T20:30:00.000000"
}
```

## 📚 Documentación Interactiva

Accede a la documentación Swagger UI en:

```
http://localhost:5000/api/docs
```

## ⚙️ Configuración

Puedes configurar las siguientes variables de entorno (ver `.env.example`):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PORT` | `5000` | Puerto del servidor |
| `DEBUG` | `false` | Modo de depuración de Flask |
| `REQUEST_TIMEOUT` | `15` | Timeout para las peticiones HTTP al BCV (segundos) |

## 🏗️ Estructura del Proyecto

```
API_BCV/
├── app.py              # Aplicación Flask principal con endpoints
├── scraper.py          # Módulo de web scraping del BCV
├── swagger.json        # Especificación OpenAPI 3.0
├── requirements.txt    # Dependencias Python
├── .env.example        # Variables de entorno de ejemplo
└── README.md           # Este archivo
```

## 🔍 Fuentes de Datos

| Dato | URL Fuente | Selector DOM |
|------|-----------|--------------|
| Tasa USD | [bcv.org.ve](https://www.bcv.org.ve/) | `#dolar strong` |
| Fecha Valor | [bcv.org.ve](https://www.bcv.org.ve/) | `span.date-display-single` |
| Fecha Índice | [Índice de Inversión](https://www.bcv.org.ve/estadisticas/indice-de-inversion) | `table tbody tr:first-child td:first-child` |
| Tasa Índice | [Índice de Inversión](https://www.bcv.org.ve/estadisticas/indice-de-inversion) | `table tbody tr:first-child td:last-child` |

## ⚠️ Notas Importantes

- **Scraping en tiempo real**: Cada llamada a la API realiza una petición HTTP al sitio del BCV. No hay caché implementado.
- **Fragilidad del scraping**: Si el BCV cambia la estructura de su sitio web, los selectores DOM podrían dejar de funcionar. La API devuelve errores descriptivos en ese caso.
- **Formatos numéricos**: Los valores numéricos se devuelven como cadenas con formato venezolano (coma decimal) para preservar la precisión y el formato original.
- **Fechas**: Todas las fechas se devuelven en formato ISO 8601 (`yyyy-MM-dd`).

## 🚀 Producción

Para desplegar en producción, usa Gunicorn:

```bash
gunicorn app:app --bind 0.0.0.0:5000 --workers 4
```
