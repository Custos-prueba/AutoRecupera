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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("autorecupera.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

# ============ CARGAR PROMPTS DESDE TXT ============

def cargar_prompt_txt(archivo):
    """Carga un prompt desde archivo txt"""
    try:
        with open(archivo, "r", encoding="utf-8") as f:
            contenido = f.read()
        log.info(f"[PROMPTS] ✓ Cargado: {archivo}")
        return contenido
    except FileNotFoundError:
        log.error(f"[PROMPTS] ✗ No existe: {archivo}")
        return None

# Cargar prompts como variables globales
PROMPT_DATOS = None
PROMPT_PIEZAS = None
PROMPT_OPERACIONES = None
PROMPT_NOTAS = None
PROMPT_IMAGENES = None

def inicializar_prompts():
    """Carga todos los prompts al inicio"""
    global PROMPT_DATOS, PROMPT_PIEZAS, PROMPT_OPERACIONES, PROMPT_NOTAS, PROMPT_IMAGENES
    
    PROMPT_DATOS = cargar_prompt_txt("prompt_datos.txt")
    PROMPT_PIEZAS = cargar_prompt_txt("prompt_piezas_txt.txt")
    PROMPT_OPERACIONES = cargar_prompt_txt("prompt_operaciones_txt.txt")
    PROMPT_NOTAS = cargar_prompt_txt("prompt_notas_txt.txt")
    PROMPT_IMAGENES = cargar_prompt_txt("prompt_imagenes_txt.txt")
    
    if all([PROMPT_DATOS, PROMPT_PIEZAS, PROMPT_OPERACIONES, PROMPT_NOTAS, PROMPT_IMAGENES]):
        log.info("[PROMPTS]  Todos los prompts cargados correctamente")
        return True
    else:
        log.warning("[PROMPTS] ⚠ Algunos prompts no se pudieron cargar")
        return False

# ============ VERIFICACIÓN DE OLLAMA ============

def verificar_ollama():
    """Verifica que Ollama está disponible"""
    try:
        log.info(f"[VERIFICACIÓN] Conectando a {OLLAMA_HOST}/api/tags...")
        inicio = time.time()
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5, verify=False)
        elapsed = time.time() - inicio
        
        if response.status_code == 200:
            log.info(f"[VERIFICACIÓN] ✓ Conectado en {elapsed:.2f}s")
            return True
        else:
            log.error(f"[VERIFICACIÓN] ✗ Status {response.status_code}")
            return False
    except Exception as e:
        log.error(f"[VERIFICACIÓN] ✗ Error: {e}")
        return False

# ============ CHAT CON OLLAMA (STREAMING) ============

def chat_ollama(model, prompt, timeout=300):
    """Envía un prompt a Ollama con streaming"""
    inicio = time.time()
    try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True
        }
        
        log.info(f"[STREAMING] {model} ({len(prompt)} chars)...")
        
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=timeout,
            verify=False,
            stream=True
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
                except:
                    pass
        
        elapsed = time.time() - inicio
        log.info(f"[STREAMING] ✓ {elapsed:.2f}s ({chunk_count} chunks, {len(respuesta_completa)} chars)")
        return respuesta_completa
            
    except requests.exceptions.Timeout:
        elapsed = time.time() - inicio
        log.error(f"[STREAMING] ✗ TIMEOUT {elapsed:.2f}s")
        return None
    except Exception as e:
        elapsed = time.time() - inicio
        log.error(f"[STREAMING] ✗ Error {elapsed:.2f}s: {e}")
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

# ============ FUNCIONES DE UTILIDAD ============

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

# ============ FUNCIONES DE EXTRACCIÓN ============

def extraer_bloque(texto, campos):
    """Extrae datos usando PROMPT_DATOS + streaming"""
    campos_str = ", ".join(campos)
    prompt = PROMPT_DATOS.format(campos=campos_str, texto=texto)
    
    log.info(f"[EXTRACCIÓN] Bloque ({len(texto)} chars, {len(campos)} campos)...")
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
    
    log.info(f"[EXTRACCIÓN] ✓ {len(campos_extraidos)} campos encontrados")
    return campos_extraidos

def extraer_piezas_sustituidas(bloques):
    """Extrae piezas sustituidas usando PROMPT_PIEZAS + streaming"""
    try:
        texto_completo = " ".join(bloques)
        prompt = PROMPT_PIEZAS.format(texto=texto_completo)
        
        respuesta = chat_ollama(MODELO_TEXTO, prompt, timeout=300)
        if not respuesta or respuesta.lower() == "null":
            return []
        
        piezas = []
        for linea in respuesta.strip().splitlines():
            if "|" in linea and "POSICIÓN" not in linea:
                partes = [p.strip() for p in linea.split("|")]
                if len(partes) >= 5:
                    piezas.append({
                        "posicion": partes[0],
                        "descripcion": partes[1],
                        "referencia": partes[2],
                        "cantidad": partes[3],
                        "precio": partes[4]
                    })
        
        log.info(f"[PIEZAS] ✓ {len(piezas)} piezas extraídas")
        return piezas
    except Exception as e:
        log.error(f"[PIEZAS] ✗ Error: {e}")
        return []

def extraer_operaciones_mo(bloques):
    """Extrae operaciones mano de obra usando PROMPT_OPERACIONES + streaming"""
    try:
        texto_completo = " ".join(bloques)
        prompt = PROMPT_OPERACIONES.format(texto=texto_completo)
        
        respuesta = chat_ollama(MODELO_TEXTO, prompt, timeout=300)
        if not respuesta or respuesta.lower() == "null":
            return []
        
        operaciones = []
        for linea in respuesta.strip().splitlines():
            if "|" in linea and "CÓDIGO" not in linea:
                partes = [p.strip() for p in linea.split("|")]
                if len(partes) >= 4:
                    operaciones.append({
                        "codigo": partes[0],
                        "descripcion": partes[1],
                        "unidades": partes[2],
                        "importe": partes[3]
                    })
        
        log.info(f"[OPERACIONES] ✓ {len(operaciones)} operaciones extraídas")
        return operaciones
    except Exception as e:
        log.error(f"[OPERACIONES] ✗ Error: {e}")
        return []

def extraer_notas_importantes(bloques):
    """Extrae notas usando PROMPT_NOTAS + streaming"""
    try:
        texto_completo = " ".join(bloques)
        prompt = PROMPT_NOTAS.format(texto=texto_completo)
        
        respuesta = chat_ollama(MODELO_TEXTO, prompt, timeout=300)
        if not respuesta or respuesta.lower() == "null":
            return []
        
        notas = []
        for linea in respuesta.strip().splitlines():
            if linea.strip() and len(linea.strip()) > 5:
                notas.append(linea.strip())
        
        log.info(f"[NOTAS] ✓ {len(notas)} notas extraídas")
        return notas
    except Exception as e:
        log.error(f"[NOTAS] ✗ Error: {e}")
        return []

def extraer_datos_texto(bloques):
    """Extrae todos los datos del texto usando streaming"""
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
    
    # Extraer piezas, operaciones y notas CON STREAMING
    with cronometro("Extracción de piezas"):
        piezas = extraer_piezas_sustituidas(bloques)
    
    with cronometro("Extracción de operaciones"):
        operaciones = extraer_operaciones_mo(bloques)
    
    with cronometro("Extracción de notas"):
        notas = extraer_notas_importantes(bloques)
    
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
        },
        "piezas_sustituidas": piezas,
        "operaciones_mano_obra": operaciones,
        "notas_importantes": notas
    }

def describir_imagenes(imagenes, datos_ya_extraidos):
    """Analiza imágenes usando PROMPT_IMAGENES + streaming"""
    if not imagenes:
        log.info("[IMG] Sin imágenes disponibles")
        return "Sin imagenes de daños disponibles."

    try:
        payload = {
            "model": MODELO_VISION,
            "messages": [{"role": "user", "content": PROMPT_IMAGENES}],
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
            log.info(f"[IMG] ✓ Análisis completado ({len(content)} chars)")
            return content
        else:
            log.error(f"[IMG] ✗ HTTP {response.status_code}")
            return "Error en análisis de imágenes"
            
    except Exception as e:
        log.error(f"[IMG] ✗ Error: {e}")
        return "Error analizando imágenes"

def procesar_pdf(archivo_pdf, password=None):
    """Procesa el PDF completo"""
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
    
    # Cargar prompts desde archivos txt como variables globales
    log.info("[MAIN] Inicializando prompts...")
    if not inicializar_prompts():
        log.warning("[MAIN] ⚠ Algunos prompts no se pudieron cargar, continuando...")

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