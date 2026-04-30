import pikepdf
import pypdf
import json
import os
import sys
import base64
from PIL import Image
import io
import time
import logging
import requests
from datetime import datetime

# ============ CONFIGURACIÓN ============

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://10.68.52.11:11434")
MODELO_TEXTO = "qwen2.5:7b"
MODELO_VISION = "qwen2.5vl:7b"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("autorecupera.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

# ============ VERIFICACIÓN DE OLLAMA ============

def verificar_ollama():
    """Verifica que Ollama está disponible"""
    try:
        log.info(f"Verificando conexión a {OLLAMA_HOST}...")
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5, verify=False)
        if response.status_code == 200:
            log.info(f"✓ Conectado a Ollama")
            return True
        else:
            log.error(f"✗ Error: Status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        log.error(f"✗ No se puede conectar a {OLLAMA_HOST}")
        return False
    except Exception as e:
        log.error(f"✗ Error: {e}")
        return False

# ============ CHAT CON OLLAMA ============

def chat_ollama(model, prompt, timeout=180):
    """Envía un prompt a Ollama y retorna la respuesta"""
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=timeout,
            verify=False
        )
        
        if response.status_code == 200:
            return response.json()['message']['content']
        else:
            log.error(f"Error: {response.status_code}")
            return None
            
    except requests.exceptions.Timeout:
        log.error(f"Timeout ({timeout}s)")
        return None
    except requests.exceptions.ConnectionError as e:
        log.error(f"Conexión rechazada: {e}")
        return None
    except Exception as e:
        log.error(f"Error: {e}")
        return None

# ============ GUARDAR JSON ============

def guardar_json(data, ruta_salida):
    """Guarda los datos en formato JSON"""
    try:
        output = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "ollama_host": OLLAMA_HOST,
                "models_used": {
                    "texto": MODELO_TEXTO,
                    "vision": MODELO_VISION
                }
            },
            "data": data
        }
        
        with open(ruta_salida, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        log.info(f"JSON guardado en: {ruta_salida}")
        return True
    except Exception as e:
        log.error(f"Error guardando JSON: {e}")
        return False

# ============ FUNCIONES DE PROCESAMIENTO ============

def cronometro(nombre):
    class Timer:
        def __enter__(self):
            self.inicio = time.time()
            log.info(f"INICIO: {nombre}")
            return self
        def __exit__(self, *args):
            self.elapsed = time.time() - self.inicio
            log.info(f"FIN: {nombre} — {self.elapsed:.2f}s")
    return Timer()

def unlock_pdf(input_path, output_path, password):
    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)
        return True
    except Exception as e:
        log.error(f"Error al desbloquear PDF: {e}")
        return False

def extraer_texto_por_bloques(pdf_path, bloque_chars=2000):
    bloques = []
    texto_acumulado = ""
    doc = pypdf.PdfReader(pdf_path)
    for page in doc.pages:
        try:
            texto_acumulado += page.extract_text() or ""
        except Exception as e:
            log.warning(f"Error extrayendo texto de página: {e}")
            continue
        if len(texto_acumulado) >= bloque_chars:
            bloques.append(texto_acumulado[:bloque_chars])
            texto_acumulado = texto_acumulado[bloque_chars:]
    if texto_acumulado.strip():
        bloques.append(texto_acumulado)
    return bloques

def redimensionar_imagen(img_bytes, max_px=512):
    img = Image.open(io.BytesIO(img_bytes))
    img.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()

def pdf_to_images(pdf_path, max_imagenes=6, min_ancho=300, min_alto=200):
    imagenes = []
    try:
        doc = pypdf.PdfReader(pdf_path)
        for page_num, page in enumerate(doc.pages):
            if len(imagenes) >= max_imagenes:
                break
            for img_index, img in enumerate(page.images):
                if len(imagenes) >= max_imagenes:
                    break
                try:
                    img_data = img.get_object()
                    width = img_data.get("/Width", 0)
                    height = img_data.get("/Height", 0)
                    if width < min_ancho or height < min_alto:
                        continue
                    img_bytes = img.get_data()
                    img_bytes = redimensionar_imagen(img_bytes, max_px=512)
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    imagenes.append(img_b64)
                    log.info(f"Imagen aceptada ({width}x{height})")
                except Exception as e:
                    log.warning(f"Error procesando imagen: {e}")
                    continue
    except Exception as e:
        log.warning(f"Error extrayendo imágenes: {e}")
    
    log.info(f"Imagenes extraidas: {len(imagenes)}")
    return imagenes

def extraer_bloque(texto, campos):
    campos_str = ", ".join(campos)
    
    prompt = f"""Eres experto extrayendo datos de documentos de seguros.
El documento puede ser de cualquier aseguradora (Audatex, AXA, Mapfre, etc).

Extrae estos campos: {campos_str}

Responde SOLO en formato:
CAMPO: valor

Si no encuentras, escribe: CAMPO: null

Documento:
{texto}
"""
    
    respuesta = chat_ollama(MODELO_TEXTO, prompt, timeout=180)
    if not respuesta:
        return {}
    
    campos_extraidos = {}
    for linea in respuesta.strip().splitlines():
        if ":" in linea:
            clave, _, valor = linea.partition(":")
            valor = valor.strip()
            if valor and valor.lower() != "null" and len(valor) < 150:
                campos_extraidos[clave.strip()] = valor
    return campos_extraidos

def extraer_datos_texto(bloques):
    campos_bloque = [
        ["nr_informe", "referencia", "fecha_informe", "fecha_siniestro",
         "fabricante", "modelo", "matricula", "bastidor", "codigo_audatransfer",
         "compromiso_pago", "codigo_tipo", "fecha_matriculacion"],
        ["km", "color", "acabado", "equipamiento", "cilindrada_cc", 
         "potencia_cv", "potencia_kw"],
        ["subtotal_piezas", "descuentos", "total_mo_chapa", "horas_mo",
         "precio_hora_chapa", "precio_hora_pintura", "total_sin_iva", 
         "iva_pct", "total_con_iva"],
    ]

    campos_acumulados = {}
    for i, bloque in enumerate(bloques[:3]):
        if i < len(campos_bloque):
            with cronometro(f"Bloque {i+1}"):
                log.info(f"Procesando bloque {i+1} ({len(bloque)} chars)...")
                resultado = extraer_bloque(bloque, campos_bloque[i])
                for k, v in resultado.items():
                    if v is not None and campos_acumulados.get(k) is None:
                        campos_acumulados[k] = v

    c = campos_acumulados
    return {
        "informe": {
            "nr_informe": c.get("nr_informe"),
            "referencia": c.get("referencia"),
            "fecha_informe": c.get("fecha_informe"),
            "fecha_siniestro": c.get("fecha_siniestro"),
            "fecha_tarifa_recambios": c.get("fecha_tarifa_recambios"),
            "codigo_audatransfer": c.get("codigo_audatransfer"),
            "compromiso_pago": c.get("compromiso_pago"),
        },
        "vehiculo": {
            "fabricante": c.get("fabricante"),
            "modelo": c.get("modelo"),
            "matricula": c.get("matricula"),
            "bastidor": c.get("bastidor"),
            "codigo_tipo": c.get("codigo_tipo"),
            "fecha_matriculacion": c.get("fecha_matriculacion"),
            "km": c.get("km"),
            "cilindrada_cc": c.get("cilindrada_cc"),
            "potencia_cv": c.get("potencia_cv"),
            "potencia_kw": c.get("potencia_kw"),
            "color": c.get("color"),
            "acabado": c.get("acabado"),
            "equipamiento": c.get("equipamiento"),
        },
        "valoracion": {
            "subtotal_piezas": c.get("subtotal_piezas"),
            "descuentos": c.get("descuentos"),
            "total_mo_chapa": c.get("total_mo_chapa"),
            "horas_mo": c.get("horas_mo"),
            "precio_hora_chapa": c.get("precio_hora_chapa"),
            "precio_hora_pintura": c.get("precio_hora_pintura"),
            "total_sin_iva": c.get("total_sin_iva"),
            "iva_pct": c.get("iva_pct"),
            "total_con_iva": c.get("total_con_iva"),
        }
    }

def describir_imagenes(imagenes, datos_ya_extraidos):
    if not imagenes:
        return "Sin imagenes de daños disponibles."

    campos_encontrados = []
    v = datos_ya_extraidos.get("vehiculo", {})
    inf = datos_ya_extraidos.get("informe", {})
    if v.get("km"):
        campos_encontrados.append(f"km ({v['km']})")
    if v.get("matricula"):
        campos_encontrados.append(f"matricula ({v['matricula']})")
    if v.get("bastidor"):
        campos_encontrados.append(f"bastidor ({v['bastidor']})")

    ya_tenemos = ""
    if campos_encontrados:
        ya_tenemos = f"\nTenemos: {', '.join(campos_encontrados)}\n"

    prompt = f"""Eres perito de seguros. Analiza estas imagenes de vehiculo siniestrado.
{ya_tenemos}
Describe daños visibles: zona, tipo, gravedad. Sé conciso, sin markdown."""

    try:
        payload = {
            "model": MODELO_VISION,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        if imagenes:
            payload["messages"][0]["images"] = imagenes
        
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=300,
            verify=False
        )
        
        if response.status_code == 200:
            return response.json()['message']['content']
        else:
            return "Error en análisis"
            
    except Exception as e:
        log.error(f"Error: {e}")
        return "Error analizando imágenes"

def procesar_pdf(archivo_pdf, password=None):
    temp_unlocked = "temp_unlocked.pdf"
    inicio_total = time.time()
    log.info(f"=== PROCESANDO: {archivo_pdf} ===")

    if password:
        if not unlock_pdf(archivo_pdf, temp_unlocked, password):
            return {"error": "No se pudo desbloquear PDF"}
        path_to_process = temp_unlocked
    else:
        path_to_process = archivo_pdf

    try:
        with cronometro("Extraccion de texto"):
            bloques = extraer_texto_por_bloques(path_to_process, bloque_chars=2000)
            log.info(f"{len(bloques)} bloques")

        if not bloques or len("".join(bloques).strip()) < 50:
            return {"error": "PDF escaneado o vacio"}

        with cronometro("Analisis de texto"):
            data = extraer_datos_texto(bloques)
        del bloques

        with cronometro("Extraccion de imagenes"):
            imagenes = pdf_to_images(path_to_process, max_imagenes=6)

        with cronometro("Descripcion de daños"):
            descripcion = describir_imagenes(imagenes, data)
        del imagenes

        data["descripcion_visual_danos"] = descripcion

        total = time.time() - inicio_total
        log.info(f"=== FIN — {total:.2f}s ===")
        return data

    except Exception as e:
        log.error(f"Error: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)

# ============ MAIN ============

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python autorecupera.py <archivo.pdf> [contraseña] [salida.json]")
        print("Ej: python autorecupera.py informe.pdf")
        sys.exit(1)

    pdf      = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    salida   = sys.argv[3] if len(sys.argv) > 3 else "resultado.json"
    
    if len(sys.argv) > 4:
        OLLAMA_HOST = sys.argv[4]

    if not os.path.exists(pdf):
        log.error(f"No existe: {pdf}")
        sys.exit(1)

    if not verificar_ollama():
        log.error("No hay conexión a Ollama")
        sys.exit(1)

    resultado = procesar_pdf(pdf, password=password)

    if "error" in resultado:
        log.error(f"Error: {resultado['error']}")
        sys.exit(1)

    guardar_json(resultado, salida)
    print(f"\n✅ Guardado: {salida}")
    
    inf = resultado.get("informe", {})
    veh = resultado.get("vehiculo", {})
    print(f"📄 Informe: {inf.get('nr_informe', 'N/A')}")
    print(f"🚗 Vehículo: {veh.get('fabricante', 'N/A')} {veh.get('modelo', 'N/A')}")
    print(f"📍 Matrícula: {veh.get('matricula', 'N/A')}")