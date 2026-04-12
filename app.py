"""
app.py — Microservicios de API para el Banco Central de Venezuela (BCV)

Aplicación Flask que expone endpoints REST para consultar datos financieros
en tiempo real del sitio web oficial del BCV.

Endpoints:
    GET /api/v1/tasa-usd          — Tasa de cambio USD y fecha de vigencia
    GET /api/v1/indice-inversion   — Índice de Inversión más reciente
    GET /api/v1/health             — Health check del servicio
    GET /api/docs                  — Documentación Swagger UI
"""

import json
import logging
import os
from datetime import datetime

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from scraper import scrape_tasa_usd, scrape_indice_inversion

# ──────────────────────────────────────────────
# Configuración
# ──────────────────────────────────────────────

app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

API_VERSION = "1.0.0"
SERVICE_NAME = "BCV API"


# ──────────────────────────────────────────────
# Endpoints de la API
# ──────────────────────────────────────────────

@app.route("/api/v1/tasa-usd", methods=["GET"])
def get_tasa_usd():
    """
    Obtiene la tasa de cambio USD y la fecha de vigencia desde el BCV.

    Returns:
        JSON con tasa_usd y fecha_valor, o un error con código HTTP apropiado.
    """
    try:
        logger.info("📊 Solicitud recibida: GET /api/v1/tasa-usd")
        data = scrape_tasa_usd()
        logger.info("✅ Tasa USD obtenida exitosamente: %s", data)
        return jsonify(data), 200

    except (ConnectionError, TimeoutError) as exc:
        logger.error("🔴 Error de conexión al obtener tasa USD: %s", exc)
        return jsonify({
            "error": str(exc),
            "status": 503,
        }), 503

    except ValueError as exc:
        logger.error("🟡 Error de parsing al obtener tasa USD: %s", exc)
        return jsonify({
            "error": str(exc),
            "status": 500,
        }), 500

    except Exception as exc:
        logger.exception("🔴 Error inesperado al obtener tasa USD: %s", exc)
        return jsonify({
            "error": f"Error interno del servidor: {exc}",
            "status": 500,
        }), 500


@app.route("/api/v1/indice-inversion", methods=["GET"])
def get_indice_inversion():
    """
    Obtiene el Índice de Inversión más reciente desde el BCV.

    Returns:
        JSON con fecha_indice y tasa_indice_nueva_expresion,
        o un error con código HTTP apropiado.
    """
    try:
        logger.info("📊 Solicitud recibida: GET /api/v1/indice-inversion")
        data = scrape_indice_inversion()
        logger.info("✅ Índice de Inversión obtenido exitosamente: %s", data)
        return jsonify(data), 200

    except (ConnectionError, TimeoutError) as exc:
        logger.error("🔴 Error de conexión al obtener índice: %s", exc)
        return jsonify({
            "error": str(exc),
            "status": 503,
        }), 503

    except ValueError as exc:
        logger.error("🟡 Error de parsing al obtener índice: %s", exc)
        return jsonify({
            "error": str(exc),
            "status": 500,
        }), 500

    except Exception as exc:
        logger.exception("🔴 Error inesperado al obtener índice: %s", exc)
        return jsonify({
            "error": f"Error interno del servidor: {exc}",
            "status": 500,
        }), 500


@app.route("/api/v1/health", methods=["GET"])
def health_check():
    """
    Health check del servicio.

    Returns:
        JSON con el estado del servicio, versión y timestamp.
    """
    return jsonify({
        "status": "ok",
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "timestamp": datetime.now().isoformat(),
    }), 200


# ──────────────────────────────────────────────
# Documentación Swagger UI
# ──────────────────────────────────────────────

@app.route("/api/docs")
def swagger_ui():
    """
    Sirve la interfaz Swagger UI para la documentación de la API.
    Utiliza SwaggerUI desde CDN para renderizar el archivo swagger.json.
    """
    swagger_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>BCV API — Documentación</title>
        <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css">
        <style>
            html { box-sizing: border-box; overflow-y: scroll; }
            *, *::before, *::after { box-sizing: inherit; }
            body { margin: 0; background: #fafafa; }
            .swagger-ui .topbar { display: none; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
        <script>
            SwaggerUIBundle({
                url: '/api/swagger.json',
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIBundle.SwaggerUIStandalonePreset
                ],
                layout: 'BaseLayout',
                deepLinking: true,
                docExpansion: 'list',
                defaultModelsExpandDepth: 1,
            });
        </script>
    </body>
    </html>
    """
    return swagger_html, 200, {"Content-Type": "text/html"}


@app.route("/api/swagger.json")
def swagger_json():
    """Sirve el archivo de especificación OpenAPI/Swagger."""
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "swagger.json",
        mimetype="application/json",
    )


# ──────────────────────────────────────────────
# Ruta raíz
# ──────────────────────────────────────────────

@app.route("/")
def index():
    """Ruta raíz con información básica del servicio."""
    return jsonify({
        "service": SERVICE_NAME,
        "version": API_VERSION,
        "description": (
            "Microservicios de API para el Banco Central de Venezuela (BCV). "
            "Consulta datos financieros en tiempo real."
        ),
        "endpoints": {
            "tasa_usd": "/api/v1/tasa-usd",
            "indice_inversion": "/api/v1/indice-inversion",
            "health": "/api/v1/health",
            "docs": "/api/docs",
        },
    }), 200


# ──────────────────────────────────────────────
# Punto de entrada
# ──────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"

    logger.info("🚀 Iniciando %s v%s en puerto %d", SERVICE_NAME, API_VERSION, port)
    app.run(host="0.0.0.0", port=port, debug=debug)
