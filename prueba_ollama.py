import fitz  # PyMuPDF
import pikepdf
import ollama
import json
import os
import imaplib
import email
import re
import tempfile
from email.header import decode_header

MODELO = "gemma3:4b"

# --- Configuración IMAP ---
IMAP_HOST = "imap.gmail.com"   # Cambia según tu proveedor
IMAP_PORT = 993
EMAIL_USER = "tu_correo@gmail.com"
EMAIL_PASS = "tu_contraseña_o_app_password"


def conectar_imap():
    mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    mail.login(EMAIL_USER, EMAIL_PASS)
    return mail


def extraer_password_del_cuerpo(cuerpo):
    match = re.search(
        r'(?:contraseña|password|clave|pwd|pass)[:\s]+([A-Za-z0-9@#$%&!_\-]+)',
        cuerpo, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def buscar_emails_con_pdf(mail, carpeta="INBOX", asunto_filtro=None):
    """Devuelve lista de (uid, asunto, cuerpo_texto, ruta_pdf_temporal)."""
    mail.select(carpeta)

    criterio = '(UNSEEN)' if not asunto_filtro else f'(UNSEEN SUBJECT "{asunto_filtro}")'
    _, uids = mail.search(None, criterio)

    resultados = []
    for uid in uids[0].split():
        _, data = mail.fetch(uid, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        # Asunto
        asunto_raw, enc = decode_header(msg["Subject"])[0]
        asunto = asunto_raw.decode(enc or "utf-8") if isinstance(asunto_raw, bytes) else asunto_raw

        # Extraer cuerpo y adjuntos
        cuerpo_texto = ""
        ruta_pdf = None

        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))

            if ct == "text/plain" and "attachment" not in cd:
                cuerpo_texto += part.get_payload(decode=True).decode(errors="ignore")

            elif ct == "application/pdf" or (
                "attachment" in cd and part.get_filename("").lower().endswith(".pdf")
            ):
                nombre = part.get_filename("adjunto.pdf")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp.write(part.get_payload(decode=True))
                tmp.close()
                ruta_pdf = tmp.name

        if ruta_pdf:
            resultados.append((uid, asunto, cuerpo_texto, ruta_pdf))

    return resultados


def procesar_correos(carpeta="INBOX", asunto_filtro=None):
    mail = conectar_imap()
    emails = buscar_emails_con_pdf(mail, carpeta, asunto_filtro)
    mail.logout()

    todos_resultados = []
    for uid, asunto, cuerpo, ruta_pdf in emails:
        print(f"\nProcesando: {asunto}")
        password = extraer_password_del_cuerpo(cuerpo)
        if password:
            print(f"  Contraseña encontrada: {password}")
        else:
            print("  Sin contraseña en el cuerpo.")

        resultado = procesar_expediente(ruta_pdf, password=password)
        resultado["_asunto"] = asunto
        todos_resultados.append(resultado)
        os.remove(ruta_pdf)  # limpia el temporal

    return todos_resultados

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

    text = response["message"]["content"]
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)

def procesar_expediente(archivo_pdf, password=None):
    temp_unlocked = "temp_unlocked.pdf"

    if password:
        if not unlock_pdf(archivo_pdf, temp_unlocked, password):
            return {"error": "No se pudo desbloquear el PDF"}
        path_to_process = temp_unlocked
    else:
        path_to_process = archivo_pdf

    try:
        print("Extrayendo texto del PDF...")
        texto = pdf_to_text(path_to_process)
        print(f"Texto extraído ({len(texto)} caracteres). Analizando con {MODELO}...")

        data = extract_data_with_ai(texto)
        return data
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)


# --- Ejemplo de uso ---
resultados = procesar_correos(asunto_filtro="Audatex")  # filtra por asunto, opcional
print(json.dumps(resultados, indent=4, ensure_ascii=False))
