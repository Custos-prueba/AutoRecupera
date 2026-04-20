import fitz  # PyMuPDF
import pikepdf
import ollama
import json
import os
import sys

MODELO = "qwen2.5vl:7b"


def unlock_pdf(input_path, output_path, password):
    try:
        with pikepdf.open(input_path, password=password) as pdf:
            pdf.save(output_path)
            return True
    except Exception as e:
        print(f"Error al desbloquear PDF: {e}")
        return False


def pdf_to_text(pdf_path):
    doc = fitz.open(pdf_path)
    texto = ""
    for page in doc:
        texto += page.get_text()
    doc.close()
    return texto


def extract_data_with_ai(texto):
    prompt = f"""
Analiza este texto de un informe Audatex y extrae SOLO este JSON, sin texto extra:

{{
  "vehiculo": {{
    "referencia": null,
    "marca": null,
    "modelo": null,
    "matricula": null,
    "bastidor": null,
    "km": null,
    "fecha_matriculacion": null
  }},
  "valoracion": {{
    "subtotal_piezas": null,
    "total_mano_obra": null,
    "total_sin_iva": null,
    "total_con_iva": null
  }},
  "daños_principales": []
}}

Responde ÚNICAMENTE con el JSON. Texto del informe:

{texto[:6000]}
"""

    response = ollama.chat(
        model=MODELO,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


def procesar_pdf(archivo_pdf, password=None):
    temp_unlocked = "temp_unlocked.pdf"

    if password:
        print(f"  Desbloqueando PDF con contraseña...")
        if not unlock_pdf(archivo_pdf, temp_unlocked, password):
            return {"error": "No se pudo desbloquear el PDF"}
        path_to_process = temp_unlocked
    else:
        path_to_process = archivo_pdf

    try:
        print("Extrayendo texto del PDF...")
        texto = pdf_to_text(path_to_process)

        if len(texto.strip()) < 50:
            return {"error": "PDF escaneado o vacío — se necesita OCR"}

        print(f"Texto extraído ({len(texto)} caracteres). Analizando con {MODELO}...")
        data = extract_data_with_ai(texto)
        return data

    except json.JSONDecodeError as e:
        return {"error": f"El modelo no devolvió JSON válido: {e}"}
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)


if __name__ == "__main__":
    print("Iniciando...")
    
    pdf = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"PDF: {pdf}")
    print(f"Existe: {os.path.exists(pdf)}")

    print("Extrayendo texto...")
    texto = pdf_to_text(pdf)
    print(f"Caracteres extraídos: {len(texto)}")

    print("Llamando a Ollama...")
    resultado = extract_data_with_ai(texto)

    print("--- RESULTADO ---")
    print(json.dumps(resultado, indent=4, ensure_ascii=False))