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
MODELO_VISION = "llava:latest" 
PROMPT_FILE = "prompt_template.txt"
PROMPT_IMAGENES_FILE = "prompt_imagenes.txt"  # ← NUEVO


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
        log.info(f"[VERIFICACIÓN] Conectando a {OLLAMA_HOST}/api/tags...")
        inicio = time.time()
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5, verify=False)
        elapsed = time.time() - inicio
        
        if response.status_code == 200:
            log.info(f"[VERIFICACIÓN]  Conectado en {elapsed:.2f}s")
            return True
        else:
            log.error(f"[VERIFICACIÓN]  Status {response.status_code}")
            return False
    except Exception as e:
        log.error(f"[VERIFICACIÓN]  Error: {e}")
        return False

# ============ CARGAR PROMPT DESDE ARCHIVO ============

def cargar_prompt_template():
    """Lee el prompt desde archivo"""
    try:
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            template = f.read()
        log.info(f"[PROMPT] Cargado desde {PROMPT_FILE}")
        return template
    except FileNotFoundError:
        log.error(f"[PROMPT] ✗ No existe {PROMPT_FILE}")
        return None

# ============ CHAT CON OLLAMA (STREAMING) ============

def chat_ollama(model, prompt, timeout=300):
    """Envía un prompt a Ollama con streaming"""
    inicio = time.time()
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True  # ← STREAMING ACTIVADO
        }
        
        log.info(f"[STREAMING] Conectando a {model} ({len(prompt)} chars)...")
        
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=timeout,
            verify=False,
            stream=True  # ← STREAMING EN requests
        )
        
        respuesta_completa = ""
        chunk_count = 0
        
        for linea in response.iter_lines():
            if linea:
                try:
                    chunk = json.loads(linea)
                    if "message" in chunk and "content" in chunk["message"]:
                        contenido = chunk["message"]["content"]
                        respuesta_completa += contenido
                        chunk_count += 1
                        # Mostrar chunks pequeños
                        if len(contenido) > 0:
                            log.info(f"[STREAMING] Chunk {chunk_count}: {contenido[:50]}...")
                except:
                    pass
        
        elapsed = time.time() - inicio
        log.info(f"[STREAMING]  Completado en {elapsed:.2f}s ({chunk_count} chunks, {len(respuesta_completa)} chars)")
        return respuesta_completa
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - inicio
        log.error(f"[STREAMING]  TIMEOUT después de {elapsed:.2f}s")
        return None
    except Exception as e:
        elapsed = time.time() - inicio
        log.error(f"[STREAMING]  Error en {elapsed:.2f}s: {e}")
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
        
        log.info(f"[JSON] Guardado en: {ruta_salida}")
        return True
    except Exception as e:
        log.error(f"[JSON] Error: {e}")
        return False

# ============ FUNCIONES DE PROCESAMIENTO ============

def cronometro(nombre):
    class Timer:
        def __enter__(self):
            self.inicio = time.time()
            log.info(f"[TIMER] INICIO: {nombre}")
            return self
        def __exit__(self, *args):
            self.elapsed = time.time() - self.inicio
            log.info(f"[TIMER] FIN: {nombre} — {self.elapsed:.2f}s")
    return Timer()

def unlock_pdf(input_path, output_path, password):
    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)
        return True
    except Exception as e:
        log.error(f"[PDF] Error al desbloquear: {e}")
        return False

def extraer_texto_por_bloques(pdf_path, bloque_chars=2000):
    bloques = []
    texto_acumulado = ""
    doc = pypdf.PdfReader(pdf_path)
    for page in doc.pages:
        try:
            texto_acumulado += page.extract_text() or ""
        except Exception as e:
            log.warning(f"[PDF] Error extrayendo página: {e}")
            continue
        if len(texto_acumulado) >= bloque_chars:
            bloques.append(texto_acumulado[:bloque_chars])
            texto_acumulado = texto_acumulado[bloque_chars:]
    if texto_acumulado.strip():
        bloques.append(texto_acumulado)
    log.info(f"[PDF] Extraídos {len(bloques)} bloques")
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
            try:
                # Nueva API de pypdf
                if "/XObject" in page["/Resources"]:
                    xobject = page["/Resources"]["/XObject"].get_object()
                    for obj_name in xobject:
                        if len(imagenes) >= max_imagenes:
                            break
                        try:
                            obj = xobject[obj_name]
                            if obj["/Subtype"] == "/Image":
                                width = int(obj.get("/Width", 0))
                                height = int(obj.get("/Height", 0))
                                
                                if width < min_ancho or height < min_alto:
                                    continue
                                
                                img_data = obj.get_data()
                                if not img_data:
                                    continue
                                
                                img_bytes = redimensionar_imagen(img_data, max_px=512)
                                img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                                imagenes.append(img_b64)
                                log.info(f"[IMG] Página {page_num+1}: Imagen ({width}x{height})")
                        except Exception as e:
                            log.debug(f"[IMG] Error procesando: {e}")
                            continue
            except Exception as e:
                log.debug(f"[IMG] Error en página: {e}")
                continue
    except Exception as e:
        log.warning(f"[IMG] Error: {e}")
    
    log.info(f"[IMG] Total: {len(imagenes)}")
    return imagenes





def extraer_bloque(texto, campos):
    """Extrae datos usando prompt desde archivo + streaming"""
    template = cargar_prompt_template()
    if not template:
        return {}
    
    campos_str = ", ".join(campos)
    prompt = template.format(campos=campos_str, texto=texto)
    
    log.info(f"[EXTRACCIÓN] Procesando bloque ({len(texto)} chars, {len(campos)} campos)...")
    respuesta = chat_ollama(MODELO_TEXTO, prompt, timeout=300)
    if not respuesta:
        return {}
    
    campos_extraidos = {}
    for linea in respuesta.strip().splitlines():
        if ":" in linea:
            clave, _, valor = linea.partition(":")
            valor = valor.strip()
            if valor and valor.lower() != "null" and len(valor) < 150:
                campos_extraidos[clave.strip()] = valor
    
    log.info(f"[EXTRACCIÓN]  Campos encontrados: {len(campos_extraidos)}")
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

def cargar_prompt_imagenes():
    """Lee el prompt de imágenes desde archivo"""
    try:
        with open(PROMPT_IMAGENES_FILE, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        log.error(f"[IMG] ✗ No existe {PROMPT_IMAGENES_FILE}")
        return None



def describir_imagenes(imagenes, datos_ya_extraidos):
    if not imagenes:
        log.info("[IMG] Sin imágenes disponibles")
        return "Sin imagenes de daños disponibles."

    prompt = cargar_prompt_imagenes()
    if not prompt:
        return "Error: prompt de imágenes no disponible"

    try:
        payload = {
            "model": MODELO_VISION,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False
        }
        
        if imagenes:
            payload["messages"][0]["images"] = imagenes
        
        log.info(f"[IMG] Analizando {len(imagenes)} imágenes con {MODELO_VISION}...")
        
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=600,
            verify=False
        )
        
        if response.status_code == 200:
            content = response.json()['message']['content']
            log.info(f"[IMG]  Análisis completado ({len(content)} chars)")
            return content
        else:
            log.error(f"[IMG]  HTTP {response.status_code}")
            return "Error en análisis de imágenes"
            
    except Exception as e:
        log.error(f"[IMG]  Error: {e}")
        return "Error analizando imágenes"





def procesar_pdf(archivo_pdf, password=None):
    temp_unlocked = "temp_unlocked.pdf"
    inicio_total = time.time()
    log.info(f"[PROCESAMIENTO] === INICIO: {archivo_pdf} ===")

    if password:
        if not unlock_pdf(archivo_pdf, temp_unlocked, password):
            return {"error": "No se pudo desbloquear PDF"}
        path_to_process = temp_unlocked
    else:
        path_to_process = archivo_pdf

    try:
        with cronometro("Extraccion de texto"):
            bloques = extraer_texto_por_bloques(path_to_process, bloque_chars=2000)

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
        log.info(f"[PROCESAMIENTO] === FIN — {total:.2f}s ===")
        return data

    except Exception as e:
        log.error(f"[PROCESAMIENTO] Error: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)

# ============ MAIN ============

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python autorecupera.py <archivo.pdf> [contraseña] [salida.json]")
        sys.exit(1)

    pdf      = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
    salida   = sys.argv[3] if len(sys.argv) > 3 else "resultado.json"
    
    if len(sys.argv) > 4:
        OLLAMA_HOST = sys.argv[4]

    if not os.path.exists(pdf):
        log.error(f"[MAIN] No existe: {pdf}")
        sys.exit(1)

    if not verificar_ollama():
        log.error("[MAIN] No hay conexión a Ollama")
        sys.exit(1)

    resultado = procesar_pdf(pdf, password=password)

    if "error" in resultado:
        log.error(f"[MAIN] Error: {resultado['error']}")
        sys.exit(1)

    guardar_json(resultado, salida)
    print(f"\n✅ Guardado: {salida}")
    
    inf = resultado.get("informe", {})
    veh = resultado.get("vehiculo", {})
    print(f"📄 Informe: {inf.get('nr_informe', 'N/A')}")
    print(f"🚗 Vehículo: {veh.get('fabricante', 'N/A')} {veh.get('modelo', 'N/A')}")
    print(f"📍 Matrícula: {veh.get('matricula', 'N/A')}")
    print("\n📋 Ver logs en: autorecupera.log")