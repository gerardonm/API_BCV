# Guía: Integración de BCV API con Power Automate Cloud

Esta guía explica cómo conectar la API del BCV desplegada en **Render.com** con Power Automate Cloud.

## 1. URL Base de la API (Producción)

Tu API está desplegada en Render y responde **en tiempo real** (sin caché, sin archivos estáticos).

> [!IMPORTANT]
> Reemplaza `bcv-api-xxxx` con el subdominio real que Render te asigne al desplegar.

- **Tasa USD:** `https://bcv-api-xxxx.onrender.com/api/v1/tasa-usd`
- **Índice de Inversión:** `https://bcv-api-xxxx.onrender.com/api/v1/indice-inversion`
- **Otras Monedas:** `https://bcv-api-xxxx.onrender.com/api/v1/otras-monedas`
- **Health Check:** `https://bcv-api-xxxx.onrender.com/api/v1/health`
- **Documentación Swagger:** `https://bcv-api-xxxx.onrender.com/api/docs`

## 2. Configuración del Conector HTTP en Power Automate

### Endpoint: Tasa USD

- **Método:** GET
- **URL:** `https://bcv-api-xxxx.onrender.com/api/v1/tasa-usd`
- **Esquema JSON (para el paso "Analizar JSON"):**

```json
{
  "type": "object",
  "properties": {
    "tasa_usd": { "type": "string" },
    "fecha_valor": { "type": "string" }
  }
}
```

### Endpoint: Índice de Inversión

- **Método:** GET
- **URL:** `https://bcv-api-xxxx.onrender.com/api/v1/indice-inversion`
- **Esquema JSON (para el paso "Analizar JSON"):**

```json
{
  "type": "object",
  "properties": {
    "fecha_indice": { "type": "string" },
    "tasa_indice_nueva_expresion": { "type": "string" }
  }
}
```

### Endpoint: Otras Monedas

- **Método:** GET
- **URL:** `https://bcv-api-xxxx.onrender.com/api/v1/otras-monedas`
- **Esquema JSON (para el paso "Analizar JSON"):**

```json
{
  "type": "object",
  "properties": {
    "fecha_valor": { "type": "string" },
    "tasas": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "codigo_moneda": { "type": "string" },
          "tasa_bs": { "type": "string" }
        }
      }
    }
  }
}
```

## 3. Cold Start (Arranque en frío)

> [!WARNING]
> En el plan gratuito de Render, el servicio se **duerme** si no recibe visitas en ~15 minutos. La primera petición después de estar dormido tardará **30-60 segundos** mientras arranca.

### Solución recomendada para Power Automate:

Configura tu flujo de Power Automate para que **2-3 minutos antes** de necesitar los datos, haga un "calentamiento" de la API:

1. **4:27 PM** → Acción HTTP GET al endpoint `/api/v1/health` (esto despierta el servidor)
2. **Esperar 2 minutos** (acción "Retraso")
3. **4:29 PM** → Acción HTTP GET al endpoint que necesites (`/api/v1/indice-inversion`, etc.)

De esta forma, cuando llegue la petición real de datos a las 4:29-4:30 PM, el servidor ya estará despierto y responderá al instante.

## 4. Tips de Power Automate

- **Control de Errores:** Configura "Ejecutar después de" (Run after) en caso de que el sitio del BCV esté caído (Error 503).
- **Tiempo límite HTTP:** Aumenta el timeout de la acción HTTP a **120 segundos** para dar margen al cold start.
- **Conversión de Tipos:** Power Automate recibirá los números como texto. Si necesitas hacer cálculos, usa la expresión `float(replace(body('Analizar_JSON')?['tasa_usd'], ',', '.'))` para convertir la coma en punto decimal.
- **Reintentos:** Configura la política de reintentos de la acción HTTP con 2-3 reintentos e intervalo de 30 segundos.

## 5. Ventajas de esta Arquitectura

| Aspecto | GitHub Pages (anterior) | Render API (actual) |
|---------|------------------------|---------------------|
| Datos | Estáticos (cada 3h) | **Tiempo real** |
| Riesgo de datos viejos | Alto | **Ninguno** |
| Costo | Gratis | **Gratis** |
| Latencia primera petición | Baja | 30-60s (cold start) |
| Latencia peticiones siguientes | Baja | **Baja (<3s)** |
