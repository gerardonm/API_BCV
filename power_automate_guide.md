# Guía: Integración de BCV API con Power Automate Cloud

Esta guía explica cómo conectar los microservicios locales con Power Automate Cloud usando **GitHub Actions**.

## 1. Acceso desde la Nube (API Pública)

Al usar GitHub Actions, tus datos están disponibles públicamente y gratis en las siguientes URLs:

- **Tasa USD:** `https://<usuario>.github.io/<repositorio>/api/v1/tasa-usd.json`
- **Índice de Inversión:** `https://<usuario>.github.io/<repositorio>/api/v1/indice-inversion.json`

> [!NOTE]
> Reemplaza `<usuario>` y `<repositorio>` con tus datos de GitHub tras activar **GitHub Pages** en `Settings > Pages > Source: Deploy from a branch`.

## 2. Configuración del Conector HTTP

### Endpoint: Tasa USD

- **Método:** GET
- **URL:** `https://<usuario>.github.io/<repositorio>/api/v1/tasa-usd.json`
- **Esquema JSON (Copia y pega en el paso "Analizar JSON"):**

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
- **URL:** `https://<usuario>.github.io/<repositorio>/api/v1/indice-inversion.json`
- **Esquema JSON (Copia y pega en el paso "Analizar JSON"):**

```json
{
  "type": "object",
  "properties": {
    "fecha_indice": { "type": "string" },
    "tasa_indice_nueva_expresion": { "type": "string" }
  }
}
```

## 3. Tips de Power Automate

- **Control de Errores:** Configura "Ejecutar después de" (Run after) en caso de que el sitio del BCV esté caído (Error 503).
- **Conversión de Tipos:** Power Automate recibirá los números como texto. Si necesitas hacer cálculos, usa la expresión `float(replace(body('Analizar_JSON')?['tasa_usd'], ',', '.'))` para convertir la coma en punto decimal.
