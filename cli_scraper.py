import json
import logging
import os
from scraper import scrape_tasa_usd, scrape_indice_inversion

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def save_json(data, filename):
    """Guarda un diccionario en un archivo JSON."""
    directory = os.path.dirname(filename)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"✅ Archivo guardado: {filename}")

def main():
    logger.info("🚀 Iniciando scraping para API Estática...")
    
    # 1. Tasa USD
    try:
        tasa_data = scrape_tasa_usd()
        save_json(tasa_data, "api/v1/tasa-usd.json")
    except Exception as e:
        logger.error(f"❌ Error al obtener tasa USD: {e}")
    
    # 2. Índice de Inversión
    try:
        indice_data = scrape_indice_inversion()
        save_json(indice_data, "api/v1/indice-inversion.json")
    except Exception as e:
        logger.error(f"❌ Error al obtener índice de inversión: {e}")

if __name__ == "__main__":
    main()
