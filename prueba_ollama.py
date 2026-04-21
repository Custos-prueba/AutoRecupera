# import fitz  # PyMuPDF
# import pikepdf
# import ollama
# import json
# import os
# import sys
# import base64
# from PIL import Image
# import io

# MODELO = "qwen2.5vl:7b"


# def unlock_pdf(input_path, output_path, password):
#     try:
#         with pikepdf.open(input_path, password=password) as pdf:
#             pdf.save(output_path)
#             return True
#     except Exception as e:
#         print(f"Error al desbloquear PDF: {e}")
#         return False


# def pdf_to_text(pdf_path):
#     doc = fitz.open(pdf_path)
#     texto = ""
#     for page in doc:
#         texto += page.get_text()
#     doc.close()
#     return texto


# def redimensionar_imagen(img_bytes, max_px=512):
#     img = Image.open(io.BytesIO(img_bytes))
#     img.thumbnail((max_px, max_px))
#     buf = io.BytesIO()
#     img.save(buf, format="JPEG", quality=75)
#     return buf.getvalue()


# def pdf_to_images(pdf_path, max_imagenes=3, min_ancho=500, min_alto=400):
#     doc = fitz.open(pdf_path)
#     imagenes = []

#     for page in doc:
#         for img in page.get_images():
#             if len(imagenes) >= max_imagenes:
#                 break
#             xref = img[0]
#             base_image = doc.extract_image(xref)

#             ancho = base_image.get("width", 0)
#             alto = base_image.get("height", 0)
#             if ancho < min_ancho or alto < min_alto:
#                 print(f"  Imagen ignorada ({ancho}x{alto}) — demasiado pequeña")
#                 continue

#             img_bytes = redimensionar_imagen(base_image["image"], max_px=512)
#             img_b64 = base64.b64encode(img_bytes).decode("utf-8")
#             imagenes.append(img_b64)
#             print(f"  Imagen aceptada ({ancho}x{alto})")

#         if len(imagenes) >= max_imagenes:
#             break

#     doc.close()
#     print(f"Imagenes extraidas: {len(imagenes)}")
#     return imagenes


# def extraer_texto_por_bloques(pdf_path, bloque_chars=3000):
#     """Devuelve el texto del PDF en bloques para no cargar todo a la vez."""
#     doc = fitz.open(pdf_path)
#     bloques = []
#     texto_acumulado = ""

#     for page in doc:
#         texto_acumulado += page.get_text()
#         if len(texto_acumulado) >= bloque_chars:
#             bloques.append(texto_acumulado[:bloque_chars])
#             texto_acumulado = texto_acumulado[bloque_chars:]

#     if texto_acumulado.strip():
#         bloques.append(texto_acumulado)

#     doc.close()
#     return bloques


# def describir_imagenes(imagenes):
#     """Llamada separada solo para describir visualmente los daños."""
#     if not imagenes:
#         return "Sin imagenes de daños disponibles."

#     prompt = """Eres un perito de seguros analizando fotos de un vehiculo siniestrado.
# Describe detalladamente lo que ves en cada imagen:
# - Zona del vehiculo afectada (frontal, lateral, rueda, motor, etc.)
# - Tipo de daño visible (rotura, deformacion, rayada, etc.)
# - Gravedad aparente
# - Cualquier detalle relevante como numeros, matriculas o indicadores visibles

# Describe lo que realmente ves en las fotos, ignorando textos o marcas de agua del PDF.
# Responde en español con una descripcion clara y directa."""

#     response = ollama.chat(
#         model=MODELO,
#         messages=[{
#             "role": "user",
#             "content": prompt,
#             "images": imagenes,
#         }],
#         keep_alive=0,
#     )
#     return response.message.content


# def extraer_datos_texto(texto):
#     """Llamada separada solo para extraer datos estructurados del texto."""
#     prompt = f"""
# Eres un experto en informes de valoracion de vehiculos siniestrados del sistema Audatex.
# Analiza el siguiente texto y extrae TODOS los datos disponibles en este JSON exacto.
# Si un campo no aparece en el documento, usa null.
# IMPORTANTE: subtotal_piezas es solo el coste de repuestos. total_mo_chapa es solo la mano de obra. total_sin_iva es la suma final sin IVA.
# Responde UNICAMENTE con el JSON, sin texto adicional ni bloques de codigo.

# {{
#   "informe": {{
#     "nr_informe": null,
#     "referencia": null,
#     "fecha_informe": null,
#     "fecha_siniestro": null,
#     "fecha_tarifa_recambios": null,
#     "sistema": null,
#     "codigo_audatransfer": null,
#     "compromiso_pago": null
#   }},
#   "vehiculo": {{
#     "fabricante": null,
#     "modelo": null,
#     "matricula": null,
#     "bastidor": null,
#     "codigo_tipo": null,
#     "fecha_matriculacion": null,
#     "km": null,
#     "cilindrada_cc": null,
#     "potencia_cv": null,
#     "potencia_kw": null,
#     "color": null,
#     "acabado": null,
#     "equipamiento": null
#   }},
#   "valoracion": {{
#     "subtotal_piezas": null,
#     "descuentos": null,
#     "total_mo_chapa": null,
#     "horas_mo": null,
#     "precio_hora_chapa": null,
#     "precio_hora_pintura": null,
#     "total_sin_iva": null,
#     "iva_pct": null,
#     "total_con_iva": null
#   }},
#   "piezas_sustituidas": [
#     {{
#       "posicion": null,
#       "descripcion": null,
#       "referencia": null,
#       "cantidad": null,
#       "importe": null
#     }}
#   ],
#   "operaciones_mo": [
#     {{
#       "descripcion": null,
#       "unidades": null,
#       "importe": null
#     }}
#   ]
# }}

# Texto del informe:

# {texto}
# """

#     response = ollama.chat(
#         model=MODELO,
#         messages=[{"role": "user", "content": prompt}],
#         keep_alive=0,
#     )

#     text = response.message.content
#     text = text.replace("```json", "").replace("```", "").strip()
#     return json.loads(text)


# def procesar_pdf(archivo_pdf, password=None):
#     temp_unlocked = "temp_unlocked.pdf"

#     if password:
#         print(f"  Desbloqueando PDF con contrasena...")
#         if not unlock_pdf(archivo_pdf, temp_unlocked, password):
#             return {"error": "No se pudo desbloquear el PDF"}
#         path_to_process = temp_unlocked
#     else:
#         path_to_process = archivo_pdf

#     try:
#         # --- PASO 1: extraer texto por bloques y liberar RAM entre bloques ---
#         print("Extrayendo texto del PDF por bloques...")
#         bloques = extraer_texto_por_bloques(path_to_process, bloque_chars=3000)
#         print(f"  {len(bloques)} bloque(s) de texto encontrados.")

#         if not bloques or len("".join(bloques).strip()) < 50:
#             return {"error": "PDF escaneado o vacio - se necesita OCR"}

#         # Usamos el primer bloque con mas datos (normalmente suficiente)
#         texto_principal = bloques[0]
#         # Si hay mas bloques, añadimos hasta 3000 chars mas de piezas
#         if len(bloques) > 1:
#             texto_principal += "\n" + bloques[1][:2000]

#         # --- PASO 2: extraer datos estructurados del texto ---
#         print(f"Analizando texto con {MODELO}...")
#         data = extraer_datos_texto(texto_principal)
#         # Liberamos texto de memoria
#         del texto_principal
#         del bloques

#         # --- PASO 3: extraer y describir imagenes ---
#         print("Extrayendo imagenes del PDF...")
#         imagenes = []

#         print(f"Describiendo daños visibles con {MODELO}...")
#         descripcion = describir_imagenes(imagenes)
#         # Liberamos imagenes de memoria
#         del imagenes

#         data["descripcion_visual_danos"] = descripcion
#         return data

#     except json.JSONDecodeError as e:
#         return {"error": f"El modelo no devolvio JSON valido: {e}"}
#     except Exception as e:
#         return {"error": str(e)}
#     finally:
#         if os.path.exists(temp_unlocked):
#             os.remove(temp_unlocked)


# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("Uso: python prueba_ollama.py <archivo.pdf> [contrasena]")
#         print("Ejemplo: python prueba_ollama.py informe_audatex.pdf")
#         print("Ejemplo: python prueba_ollama.py informe_audatex.pdf mipassword123")
#         sys.exit(1)

#     pdf = sys.argv[1]
#     password = sys.argv[2] if len(sys.argv) > 2 else None

#     if not os.path.exists(pdf):
#         print(f"Error: no se encuentra el archivo {pdf}")
#         sys.exit(1)

#     print(f"\nProcesando: {pdf}")
#     resultado = procesar_pdf(pdf, password=password)

#     print("\n--- RESULTADO ---")
#     print(json.dumps(resultado, indent=4, ensure_ascii=False))

#     salida = pdf.replace(".pdf", "_resultado.json")
#     with open(salida, "w", encoding="utf-8") as f:
#         json.dump(resultado, f, indent=4, ensure_ascii=False)
#     print(f"\nGuardado en: {salida}")

################################################################################################################


import fitz  # PyMuPDF
import pikepdf
import ollama
import json
import os
import sys
import base64
from PIL import Image
import io

MODELO_TEXTO = "qwen2.5:14b"
MODELO_VISION = "qwen2.5vl:7b"


def unlock_pdf(input_path, output_path, password):
    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)
            return True
    except Exception as e:
        print(f"Error al desbloquear PDF: {e}")
        return False


def extraer_texto_por_bloques(pdf_path, bloque_chars=2000):
    doc = fitz.open(pdf_path)
    bloques = []
    texto_acumulado = ""
    for page in doc:
        texto_acumulado += page.get_text()
        if len(texto_acumulado) >= bloque_chars:
            bloques.append(texto_acumulado[:bloque_chars])
            texto_acumulado = texto_acumulado[bloque_chars:]
    if texto_acumulado.strip():
        bloques.append(texto_acumulado)
    doc.close()
    return bloques


def redimensionar_imagen(img_bytes, max_px=512):
    img = Image.open(io.BytesIO(img_bytes))
    img.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()


def pdf_to_images(pdf_path, max_imagenes=6, min_ancho=300, min_alto=200):
    doc = fitz.open(pdf_path)
    imagenes = []
    for page in doc:
        for img in page.get_images():
            if len(imagenes) >= max_imagenes:
                break
            xref = img[0]
            base_image = doc.extract_image(xref)
            ancho = base_image.get("width", 0)
            alto = base_image.get("height", 0)
            if ancho < min_ancho or alto < min_alto:
                print(f"  Imagen ignorada ({ancho}x{alto}) — demasiado pequeña")
                continue
            img_bytes = redimensionar_imagen(base_image["image"], max_px=512)
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            imagenes.append(img_b64)
            print(f"  Imagen aceptada ({ancho}x{alto})")
        if len(imagenes) >= max_imagenes:
            break
    doc.close()
    print(f"Imagenes extraidas: {len(imagenes)}")
    return imagenes


CAMPOS_TODOS = [
    "nr_informe", "referencia", "fecha_informe", "fecha_siniestro",
    "fecha_tarifa_recambios", "codigo_audatransfer", "compromiso_pago",
    "fabricante", "modelo", "matricula", "bastidor", "codigo_tipo",
    "fecha_matriculacion", "km", "cilindrada_cc", "potencia_cv", "potencia_kw",
    "color", "acabado", "equipamiento", "subtotal_piezas", "descuentos",
    "total_mo_chapa", "horas_mo", "precio_hora_chapa", "precio_hora_pintura",
    "total_sin_iva", "iva_pct", "total_con_iva"
]


def extraer_bloque(texto, campos):
    """Extrae un subconjunto de campos de un bloque de texto."""
    lista_campos = "\n".join(f"{c}:" for c in campos)
    prompt = f"""Extrae del siguiente texto estos datos, uno por linea con formato CLAVE: VALOR.
Si no encuentras el dato escribe CLAVE: null
No añadas explicaciones ni texto extra.

{lista_campos}

IMPORTANTE:
- matricula es la matrícula del vehículo (ej: 3486MFC), NO el bastidor
- bastidor es el numero de chasis VIN (empieza por WB, longitud 17 caracteres)
- subtotal_piezas es solo el coste de repuestos (sin mano de obra)
- total_mo_chapa es solo la mano de obra
- total_sin_iva es la suma final sin IVA
- total_con_iva es la suma final con IVA
- acabado es el tipo de pintura (ej: BICAPA, UNICAPA)
- equipamiento son los extras del vehiculo (ej: PARABRISAS ALTO, TOP CASE)
- codigo_audatransfer es un codigo hexadecimal de 6 caracteres (ej: 88D5FB)
- fecha_siniestro es la fecha del accidente, diferente a la fecha del informe
- total_sin_iva es "SUMA TOTAL SIN IVA" en el documento
- total_con_iva es "SUMA TOTAL CON IVA" en el documento
- iva_pct es el porcentaje de IVA aplicado (ej: 21)

Texto:
{texto}
"""
    response = ollama.chat(
        model=MODELO_TEXTO,
        messages=[{"role": "user", "content": prompt}],
        keep_alive=0,
    )

    lineas = response.message.content.strip().splitlines()
    campos_extraidos = {}
    for linea in lineas:
        if ":" in linea:
            clave, _, valor = linea.partition(":")
            valor = valor.strip()
            campos_extraidos[clave.strip()] = None if valor.lower() in ("null", "") else valor
    return campos_extraidos


def extraer_datos_texto(bloques):
    """Procesa cada bloque por separado y combina los resultados."""
    # Campos que buscamos en cada bloque
    campos_bloque = [
        # Bloque 1: datos generales del informe y vehículo
        ["nr_informe", "referencia", "fecha_informe", "fecha_siniestro",
         "fabricante", "modelo", "matricula", "bastidor", "compromiso_pago"],
        # Bloque 2: datos técnicos del vehículo y valoración
        ["fecha_matriculacion", "km", "cilindrada_cc", "potencia_cv", "potencia_kw",
         "color", "acabado", "equipamiento", "codigo_tipo", "fecha_tarifa_recambios",
         "codigo_audatransfer"],
        # Bloque 3: valoración económica
        ["subtotal_piezas", "descuentos", "total_mo_chapa", "horas_mo",
         "precio_hora_chapa", "precio_hora_pintura", "total_sin_iva", "iva_pct",
         "total_con_iva"],
    ]

    campos_acumulados = {}
    for i, bloque in enumerate(bloques[:3]):
        if i < len(campos_bloque):
            print(f"  Procesando bloque {i+1} ({len(bloque)} chars)...")
            resultado = extraer_bloque(bloque, campos_bloque[i])
            # Solo guardamos valores no nulos, sin sobreescribir los que ya tenemos
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
        },
        "piezas_sustituidas": [],
        "operaciones_mo": []
    }


def describir_imagenes(imagenes):
    """Usa qwen2.5vl:7b — describe daños en texto plano sin markdown."""
    if not imagenes:
        return "Sin imagenes de daños disponibles."

    prompt = """Eres un perito de seguros analizando fotos de un vehiculo siniestrado.
De todas las imagenes que ves, identifica cuales muestran daños fisicos al vehiculo.
Para cada imagen con daños describe la zona afectada, tipo y gravedad del daño.
Si ves matricula, VIN, kilometros o datos tecnicos, extráelos tambien.
Ignora imagenes que solo muestren documentos, sellos o texto del PDF.
Responde en español en texto plano, sin asteriscos, sin markdown, sin formato especial.
Se directo y conciso."""

    response = ollama.chat(
        model=MODELO_VISION,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": imagenes,
        }],
        keep_alive=0,
    )
    return response.message.content


def procesar_pdf(archivo_pdf, password=None):
    temp_unlocked = "temp_unlocked.pdf"

    if password:
        print(f"  Desbloqueando PDF con contrasena...")
        if not unlock_pdf(archivo_pdf, temp_unlocked, password):
            return {"error": "No se pudo desbloquear el PDF"}
        path_to_process = temp_unlocked
    else:
        path_to_process = archivo_pdf

    try:
        # --- PASO 1: extraer texto por bloques ---
        print("Extrayendo texto del PDF por bloques...")
        bloques = extraer_texto_por_bloques(path_to_process, bloque_chars=2000)
        print(f"  {len(bloques)} bloque(s) de texto encontrados.")

        if not bloques or len("".join(bloques).strip()) < 50:
            return {"error": "PDF escaneado o vacio - se necesita OCR"}

        # --- PASO 2: procesar cada bloque por separado ---
        print(f"Analizando bloques con {MODELO_TEXTO}...")
        data = extraer_datos_texto(bloques)
        del bloques

        # --- PASO 3: imagenes con modelo de vision ---
        print("Extrayendo imagenes del PDF...")
        imagenes = pdf_to_images(path_to_process, max_imagenes=6, min_ancho=300, min_alto=200)

        print(f"Describiendo daños visibles con {MODELO_VISION}...")
        descripcion = describir_imagenes(imagenes)
        del imagenes

        data["descripcion_visual_danos"] = descripcion
        return data

    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python prueba_ollama.py <archivo.pdf> [contrasena]")
        print("Ejemplo: python prueba_ollama.py informe_audatex.pdf")
        print("Ejemplo: python prueba_ollama.py informe_audatex.pdf mipassword123")
        sys.exit(1)

    pdf = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(pdf):
        print(f"Error: no se encuentra el archivo {pdf}")
        sys.exit(1)

    print(f"\nProcesando: {pdf}")
    resultado = procesar_pdf(pdf, password=password)

    print("\n--- RESULTADO ---")
    print(json.dumps(resultado, indent=4, ensure_ascii=False))

    salida = pdf.replace(".pdf", "_resultado.json")
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=4, ensure_ascii=False)
    print(f"\nGuardado en: {salida}")