"""
scraper.py — Módulo de Web Scraping para el Banco Central de Venezuela (BCV)

Extrae datos financieros en tiempo real del sitio web oficial del BCV:
- Tasa de cambio USD y fecha de vigencia
- Índice de Inversión (Base=28/10/2019) y fecha
- Tasas de Otras Monedas (descarga y procesamiento de Excel en memoria)
"""

import io
import re
import time
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────

BCV_HOME_URL = "https://www.bcv.org.ve/"
BCV_INDICE_URL = "https://www.bcv.org.ve/estadisticas/indice-de-inversion"
BCV_OTRAS_MONEDAS_URL = "https://www.bcv.org.ve/estadisticas/otras-monedas"

REQUEST_TIMEOUT = 30  # segundos (aumentado para conexiones desde la nube)
MAX_RETRIES = 3       # número de reintentos ante fallas de conexión
RETRY_BASE_DELAY = 2  # segundos base entre reintentos (backoff exponencial)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "es-VE,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.bcv.org.ve/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
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

def _create_session() -> requests.Session:
    """
    Crea una sesión HTTP que persiste cookies entre peticiones.
    Esto es crucial para superar la verificación anti-bot del BCV
    (Imperva/Incapsula), que requiere que los cookies de la primera
    visita se reenvíen en peticiones subsiguientes.
    """
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def _fetch_page(url: str) -> BeautifulSoup:
    """
    Descarga y parsea una página web del BCV con reintentos automáticos.

    Implementa una estrategia de backoff exponencial para manejar
    bloqueos temporales del firewall del BCV (Imperva/Incapsula) y
    errores de conexión desde servidores en la nube.
    
    Añade un parámetro dinámico para romper el caché perimetral.

    Args:
        url: URL de la página a descargar.

    Returns:
        Objeto BeautifulSoup con el HTML parseado.

    Raises:
        ConnectionError: Si no se puede conectar tras MAX_RETRIES intentos.
        TimeoutError: Si la conexión excede el tiempo límite.
        ValueError: Si la respuesta HTTP no es exitosa.
    """
    session = _create_session()
    last_exception = None
    
    # ── Forzar Bypass de Caché CDN/Firewall ──
    # Se agrega un timestamp único a la URL para obligar al BCV a servir data fresca.
    sep = "&" if "?" in url else "?"
    cache_busting_url = f"{url}{sep}nocache={int(time.time())}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Intento %d/%d — Conectando a %s", attempt, MAX_RETRIES, cache_busting_url
            )
            response = session.get(cache_busting_url, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                logger.info("Conexión exitosa a %s (intento %d)", url, attempt)
                return BeautifulSoup(response.text, "lxml")

            # Códigos 403/503 pueden ser bloqueos temporales del firewall
            if response.status_code in (403, 503) and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP %d de %s — Reintentando en %ds (intento %d/%d)",
                    response.status_code, url, delay, attempt, MAX_RETRIES,
                )
                time.sleep(delay)
                continue

            # Error HTTP no recuperable
            logger.error("Respuesta HTTP %d de %s", response.status_code, url)
            raise ValueError(
                f"Respuesta HTTP {response.status_code} de {url}"
            )

        except requests.exceptions.Timeout:
            last_exception = TimeoutError(
                f"Timeout al conectar con {url} (>{REQUEST_TIMEOUT}s)"
            )
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Timeout en %s — Reintentando en %ds (intento %d/%d)",
                    url, delay, attempt, MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            logger.error("Timeout al conectar con %s tras %d intentos", url, MAX_RETRIES)
            raise last_exception

        except requests.exceptions.ConnectionError as exc:
            last_exception = ConnectionError(
                f"No se pudo conectar con {url}"
            )
            last_exception.__cause__ = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Error de conexión con %s — Reintentando en %ds (intento %d/%d)",
                    url, delay, attempt, MAX_RETRIES,
                )
                time.sleep(delay)
                continue
            logger.error(
                "Error de conexión con %s tras %d intentos: %s",
                url, MAX_RETRIES, exc,
            )
            raise last_exception from exc

        except requests.exceptions.RequestException as exc:
            logger.error("Error HTTP al solicitar %s: %s", url, exc)
            raise ConnectionError(f"Error al solicitar {url}: {exc}") from exc

    # Fallback: si se agotaron los reintentos sin lanzar excepción
    raise last_exception or ConnectionError(
        f"No se pudo conectar con {url} tras {MAX_RETRIES} intentos"
    )


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


def scrape_otras_monedas() -> dict:
    """
    Extrae las tasas de cambio de "Otras Monedas" desde el archivo Excel del BCV.

    Proceso:
        1. Scrapea la página para encontrar el enlace de descarga del Excel.
        2. Descarga el archivo Excel en memoria (BytesIO).
        3. Lee la primera hoja con pandas (fecha más reciente).
        4. Extrae la "Fecha Valor" de las celdas de encabezado.
        5. Limpia y transforma los datos de monedas.

    Fuente: https://www.bcv.org.ve/estadisticas/otras-monedas

    Returns:
        dict con las claves:
            - "fecha_valor": str — Fecha en formato yyyy-MM-dd
            - "tasas": list[dict] — Lista de monedas con codigo_moneda y tasa_bs

    Raises:
        ConnectionError: Si no se puede acceder al sitio del BCV.
        TimeoutError: Si la solicitud excede el tiempo límite.
        ValueError: Si no se encuentra el Excel o los datos no son válidos.
    """
    logger.info(
        "Iniciando scraping de Otras Monedas desde %s", BCV_OTRAS_MONEDAS_URL
    )

    # ── Paso 1: Encontrar el enlace de descarga del Excel ──
    soup = _fetch_page(BCV_OTRAS_MONEDAS_URL)

    excel_link = None
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if re.search(r"\.xlsx?$", href, re.IGNORECASE):
            excel_link = href
            break

    if not excel_link:
        raise ValueError(
            "No se encontró el enlace de descarga del archivo Excel "
            "en la página de Otras Monedas del BCV."
        )

    # Construir URL absoluta si es relativa
    if excel_link.startswith("/"):
        excel_link = urljoin(BCV_HOME_URL, excel_link)

    logger.info("Enlace del Excel encontrado: %s", excel_link)

    # ── Paso 2: Descargar el archivo en memoria (con reintentos) ──
    session = _create_session()
    response = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                "Descargando Excel (intento %d/%d): %s",
                attempt, MAX_RETRIES, excel_link,
            )
            response = session.get(excel_link, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                break
            if response.status_code in (403, 503) and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "HTTP %d al descargar Excel — Reintentando en %ds",
                    response.status_code, delay,
                )
                time.sleep(delay)
                continue
        except requests.exceptions.Timeout:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("Timeout descargando Excel — Reintentando en %ds", delay)
                time.sleep(delay)
                continue
            raise TimeoutError(
                f"Timeout al descargar el Excel desde {excel_link} "
                f"(>{REQUEST_TIMEOUT}s)"
            )
        except requests.exceptions.RequestException as exc:
            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning("Error descargando Excel — Reintentando en %ds", delay)
                time.sleep(delay)
                continue
            raise ConnectionError(
                f"Error al descargar el Excel desde {excel_link}: {exc}"
            ) from exc

    if response is None or response.status_code != 200:
        raise ValueError(
            f"No se pudo descargar el Excel desde {excel_link} "
            f"tras {MAX_RETRIES} intentos"
        )

    excel_bytes = io.BytesIO(response.content)
    logger.info("Excel descargado en memoria (%d bytes)", len(response.content))

    # ── Paso 3: Leer la primera hoja con pandas ──
    try:
        # Determinar el engine según la extensión
        engine = "xlrd" if excel_link.lower().endswith(".xls") else "openpyxl"
        df_raw = pd.read_excel(
            excel_bytes, sheet_name=0, header=None, engine=engine
        )
    except Exception as exc:
        raise ValueError(
            f"Error al leer el archivo Excel: {exc}"
        ) from exc

    logger.info(
        "Excel leído: %d filas x %d columnas", len(df_raw), len(df_raw.columns)
    )

    # ── Paso 4: Extraer la Fecha Valor ──
    # La fila 4 (índice 4) contiene: "Fecha Valor:  DD/MM/YYYY" en la columna 3
    fecha_valor = None

    for row_idx in range(min(10, len(df_raw))):
        for col_idx in range(len(df_raw.columns)):
            cell = df_raw.iloc[row_idx, col_idx]
            if isinstance(cell, str) and "fecha valor" in cell.lower():
                # Extraer la fecha del texto: "Fecha Valor:  13/04/2026"
                match = re.search(r"(\d{2})/(\d{2})/(\d{4})", cell)
                if match:
                    dia = match.group(1)
                    mes = match.group(2)
                    anio = match.group(3)
                    fecha_valor = f"{anio}-{mes}-{dia}"
                    break
        if fecha_valor:
            break

    if not fecha_valor:
        raise ValueError(
            "No se encontró la 'Fecha Valor' en las primeras filas del Excel."
        )

    logger.info("Fecha Valor extraída: %s", fecha_valor)

    # ── Paso 5: Encontrar la fila de encabezados de datos ──
    # Buscar la fila que contiene "Moneda" o los encabezados de la tabla
    # En el Excel del BCV, la estructura es:
    #   Col 1 = Código moneda, Col 2 = País,
    #   Col 3 = Compra M.E./US$, Col 4 = Venta M.E./US$,
    #   Col 5 = Compra Bs./M.E., Col 6 = Venta Bs./M.E.
    # Los datos comienzan típicamente en la fila 10 (índice 10)

    # Encontrar dónde empiezan los datos de monedas
    data_start = None
    for i in range(len(df_raw)):
        cell_1 = df_raw.iloc[i, 1] if pd.notna(df_raw.iloc[i, 1]) else ""
        # Los datos de monedas tienen códigos de 3 letras en la columna 1
        if isinstance(cell_1, str) and re.match(r"^[A-Z]{3}$", cell_1.strip()):
            data_start = i
            break

    if data_start is None:
        raise ValueError(
            "No se encontraron datos de monedas en el archivo Excel. "
            "Es posible que el formato haya cambiado."
        )

    logger.info("Datos de monedas encontrados a partir de la fila %d", data_start)

    # ── Paso 6: Extraer y limpiar datos de monedas ──
    tasas = []
    for i in range(data_start, len(df_raw)):
        codigo = df_raw.iloc[i, 1]

        # Verificar que sea un código de moneda válido (3 letras mayúsculas)
        if not isinstance(codigo, str) or not re.match(
            r"^[A-Z]{3}$", codigo.strip()
        ):
            # Si encontramos "NOTAS:" u otra cosa, terminamos
            if isinstance(codigo, str) and "nota" in codigo.lower():
                break
            continue

        codigo = codigo.strip()

        # Obtener la tasa Bs./M.E. (columna Venta ASK = última columna útil)
        # Col 5 = Compra (BID) Bs./M.E., Col 6 = Venta (ASK) Bs./M.E.
        tasa_bs_venta = df_raw.iloc[i, 6]  # Venta ASK en Bs./M.E.

        # Si la tasa de venta no es numérica, intentar con la de compra
        if pd.isna(tasa_bs_venta) or str(tasa_bs_venta).strip() == "----------------":
            tasa_bs_compra = df_raw.iloc[i, 5]
            if pd.notna(tasa_bs_compra) and str(tasa_bs_compra).strip() != "----------------":
                tasa_bs = str(tasa_bs_compra)
            else:
                continue  # Saltar monedas sin tasa en Bs.
        else:
            tasa_bs = str(tasa_bs_venta)

        # Limpiar y formatear la tasa
        tasa_bs = tasa_bs.strip()

        tasas.append({
            "codigo_moneda": codigo,
            "tasa_bs": tasa_bs,
        })

    if not tasas:
        raise ValueError(
            "No se pudieron extraer tasas de monedas del archivo Excel."
        )

    logger.info("Se extrajeron %d tasas de monedas", len(tasas))

    return {
        "fecha_valor": fecha_valor,
        "tasas": tasas,
    }

