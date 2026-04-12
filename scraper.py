"""
scraper.py — Módulo de Web Scraping para el Banco Central de Venezuela (BCV)

Extrae datos financieros en tiempo real del sitio web oficial del BCV:
- Tasa de cambio USD y fecha de vigencia
- Índice de Inversión (Base=28/10/2019) y fecha
"""

import re
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────

BCV_HOME_URL = "https://www.bcv.org.ve/"
BCV_INDICE_URL = "https://www.bcv.org.ve/estadisticas/indice-de-inversion"

REQUEST_TIMEOUT = 15  # segundos

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Diccionario de meses en español → número
MESES_ES = {
    "enero": "01",
    "febrero": "02",
    "marzo": "03",
    "abril": "04",
    "mayo": "05",
    "junio": "06",
    "julio": "07",
    "agosto": "08",
    "septiembre": "09",
    "octubre": "10",
    "noviembre": "11",
    "diciembre": "12",
}


# ──────────────────────────────────────────────
# Funciones auxiliares
# ──────────────────────────────────────────────

def _fetch_page(url: str) -> BeautifulSoup:
    """
    Descarga y parsea una página web del BCV.

    Args:
        url: URL de la página a descargar.

    Returns:
        Objeto BeautifulSoup con el HTML parseado.

    Raises:
        ConnectionError: Si no se puede conectar al sitio.
        TimeoutError: Si la conexión excede el tiempo límite.
        ValueError: Si la respuesta HTTP no es exitosa.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        logger.error("Timeout al conectar con %s", url)
        raise TimeoutError(f"Timeout al conectar con {url} (>{REQUEST_TIMEOUT}s)")
    except requests.exceptions.ConnectionError as exc:
        logger.error("Error de conexión con %s: %s", url, exc)
        raise ConnectionError(f"No se pudo conectar con {url}") from exc
    except requests.exceptions.RequestException as exc:
        logger.error("Error HTTP al solicitar %s: %s", url, exc)
        raise ConnectionError(f"Error al solicitar {url}: {exc}") from exc

    if response.status_code != 200:
        logger.error("Respuesta HTTP %d de %s", response.status_code, url)
        raise ValueError(
            f"Respuesta HTTP {response.status_code} de {url}"
        )

    return BeautifulSoup(response.text, "lxml")


def _transformar_fecha_larga(fecha_texto: str) -> str:
    """
    Transforma una fecha en formato largo del BCV a formato yyyy-MM-dd.

    Ejemplo:
        "Lunes, 13 Abril 2026" → "2026-04-13"

    Args:
        fecha_texto: Texto con la fecha en formato largo español.

    Returns:
        Fecha en formato "yyyy-MM-dd".

    Raises:
        ValueError: Si el formato de la fecha no es reconocido.
    """
    # Eliminar prefijo "Fecha Valor: " si existe
    texto = fecha_texto.strip()
    if texto.lower().startswith("fecha valor:"):
        texto = texto[len("fecha valor:"):].strip()

    # Eliminar el día de la semana: "Lunes, " → ""
    # Buscar patrón: "DíaSemana, DD Mes YYYY"
    match = re.match(
        r"(?:\w+,?\s+)?(\d{1,2})\s+(\w+)\s+(\d{4})",
        texto,
        re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Formato de fecha no reconocido: '{fecha_texto}'")

    dia = match.group(1).zfill(2)
    mes_nombre = match.group(2).lower()
    anio = match.group(3)

    mes_num = MESES_ES.get(mes_nombre)
    if not mes_num:
        raise ValueError(
            f"Mes no reconocido: '{mes_nombre}' en la fecha '{fecha_texto}'"
        )

    return f"{anio}-{mes_num}-{dia}"


def _transformar_fecha_corta(fecha_texto: str) -> str:
    """
    Transforma una fecha en formato dd-MM-yyyy a yyyy-MM-dd.

    Ejemplo:
        "10-04-2026" → "2026-04-10"

    Args:
        fecha_texto: Texto con la fecha en formato dd-MM-yyyy.

    Returns:
        Fecha en formato "yyyy-MM-dd".

    Raises:
        ValueError: Si el formato de la fecha no es reconocido.
    """
    texto = fecha_texto.strip()
    match = re.match(r"(\d{2})-(\d{2})-(\d{4})", texto)
    if not match:
        raise ValueError(f"Formato de fecha corta no reconocido: '{fecha_texto}'")

    dia = match.group(1)
    mes = match.group(2)
    anio = match.group(3)

    return f"{anio}-{mes}-{dia}"


# ──────────────────────────────────────────────
# Funciones principales de scraping
# ──────────────────────────────────────────────

def scrape_tasa_usd() -> dict:
    """
    Extrae la tasa de cambio USD y la fecha de vigencia del BCV.

    Fuente: https://www.bcv.org.ve/

    Returns:
        dict con las claves:
            - "tasa_usd": str — Valor numérico de la tasa (ej. "477,14880000")
            - "fecha_valor": str — Fecha en formato yyyy-MM-dd (ej. "2026-04-13")

    Raises:
        ConnectionError: Si no se puede acceder al sitio del BCV.
        TimeoutError: Si la solicitud excede el tiempo límite.
        ValueError: Si no se encuentran los datos esperados en la página.
    """
    logger.info("Iniciando scraping de tasa USD desde %s", BCV_HOME_URL)

    soup = _fetch_page(BCV_HOME_URL)

    # ── Extraer tasa USD ──
    # Selector: #dolar strong
    dolar_div = soup.find(id="dolar")
    if not dolar_div:
        raise ValueError(
            "No se encontró el elemento #dolar en la página del BCV. "
            "Es posible que la estructura del sitio haya cambiado."
        )

    strong_tag = dolar_div.find("strong")
    if not strong_tag:
        raise ValueError(
            "No se encontró el valor de la tasa USD dentro del elemento #dolar."
        )

    tasa_usd = strong_tag.get_text(strip=True)
    if not tasa_usd:
        raise ValueError("El valor de la tasa USD está vacío.")

    logger.info("Tasa USD extraída: %s", tasa_usd)

    # ── Extraer fecha de vigencia ──
    # Selector: span.date-display-single (dentro del contexto del tipo de cambio)
    # Buscar dentro del contenedor del tipo de cambio si es posible
    tipo_cambio_container = soup.find(
        "div", class_="view-tipo-de-cambio-oficial-del-bcv"
    )

    fecha_span = None
    if tipo_cambio_container:
        fecha_span = tipo_cambio_container.find(
            "span", class_="date-display-single"
        )

    # Fallback: buscar en todo el documento
    if not fecha_span:
        fecha_span = soup.find("span", class_="date-display-single")

    if not fecha_span:
        raise ValueError(
            "No se encontró la fecha de vigencia (span.date-display-single) "
            "en la página del BCV."
        )

    fecha_texto = fecha_span.get_text(strip=True)
    logger.info("Fecha de vigencia extraída (raw): %s", fecha_texto)

    fecha_valor = _transformar_fecha_larga(fecha_texto)
    logger.info("Fecha de vigencia transformada: %s", fecha_valor)

    return {
        "tasa_usd": tasa_usd,
        "fecha_valor": fecha_valor,
    }


def scrape_indice_inversion() -> dict:
    """
    Extrae la fecha y tasa del Índice de Inversión más reciente del BCV.

    Fuente: https://www.bcv.org.ve/estadisticas/indice-de-inversion

    Returns:
        dict con las claves:
            - "fecha_indice": str — Fecha en formato yyyy-MM-dd (ej. "2026-04-10")
            - "tasa_indice_nueva_expresion": str — Valor numérico (ej. "2,32926182")

    Raises:
        ConnectionError: Si no se puede acceder al sitio del BCV.
        TimeoutError: Si la solicitud excede el tiempo límite.
        ValueError: Si no se encuentran los datos esperados en la tabla.
    """
    logger.info("Iniciando scraping de índice de inversión desde %s", BCV_INDICE_URL)

    soup = _fetch_page(BCV_INDICE_URL)

    # ── Buscar la tabla de datos ──
    # Selector: table.views-table
    table = soup.find("table", class_="views-table")
    if not table:
        # Fallback: cualquier tabla con tbody
        table = soup.find("table")

    if not table:
        raise ValueError(
            "No se encontró la tabla de índice de inversión en la página del BCV. "
            "Es posible que la estructura del sitio haya cambiado."
        )

    tbody = table.find("tbody")
    if not tbody:
        raise ValueError(
            "No se encontró el cuerpo (tbody) de la tabla de índice de inversión."
        )

    # ── Extraer la primera fila de datos ──
    first_row = tbody.find("tr")
    if not first_row:
        raise ValueError(
            "No se encontraron filas de datos en la tabla de índice de inversión."
        )

    cells = first_row.find_all("td")
    if len(cells) < 2:
        raise ValueError(
            f"La primera fila de datos tiene {len(cells)} columnas, "
            "se esperaban al menos 2."
        )

    # ── Extraer fecha (primera columna) ──
    fecha_raw = cells[0].get_text(strip=True)
    logger.info("Fecha del índice extraída (raw): %s", fecha_raw)

    fecha_indice = _transformar_fecha_corta(fecha_raw)
    logger.info("Fecha del índice transformada: %s", fecha_indice)

    # ── Extraer tasa (última columna) ──
    tasa_raw = cells[-1].get_text(strip=True)
    if not tasa_raw:
        raise ValueError("El valor del índice de inversión está vacío.")

    logger.info("Tasa índice nueva expresión extraída: %s", tasa_raw)

    return {
        "fecha_indice": fecha_indice,
        "tasa_indice_nueva_expresion": tasa_raw,
    }
