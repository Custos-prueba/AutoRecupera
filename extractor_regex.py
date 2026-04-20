import fitz
import pikepdf
import json
import re
import os


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
    texto = "\n".join(page.get_text() for page in doc)
    doc.close()
    return texto

def buscar(patron, texto, grupo=1, flags=re.IGNORECASE):
    m = re.search(patron, texto, flags)
    return m.group(grupo).strip() if m else None

def extraer_datos(texto):
    return {
        "referencia": buscar(r'REFERENCIA\s*\n([^\n]+)', texto),
        "nr_informe": buscar(r'NR\s*\n([A-Z0-9]+)', texto),
        "fecha_informe": buscar(r'NR\s*\n[A-Z0-9]+\s*\n(\d{2}/\d{2}/\d{4})', texto),
        "fecha_siniestro": buscar(r'FECHA DE SINIESTRO\s*\n(\d{2}/\d{2}/\d{4})', texto),
        "sistema_valoracion": "AUDATEX",
        "compromiso_pago": "SIN COMPROMISO DE PAGO" not in texto,
        "vehiculo": {
            "fabricante": buscar(r'FABRICANTE\s*\n([^\n]+)', texto),
            "modelo": buscar(r'MODELO / TIPO\s*\n([^\n]+)', texto),
            "matricula": buscar(r'MATRICULA\s*\n([^\n]+)', texto),
            "vin": buscar(r'N[ÚU]MERO CHASIS\s*\n([^\n]+)', texto),
            "fecha_matriculacion": buscar(r'FECHA MATRICULACI[ÓO]N\s*\n(\d{2}/\d{2}/\d{4})', texto),
            "kilometros": buscar(r'KIL[ÓO]METROS\s*\n(\d+)', texto),
        },
        "valoracion": {
            "subtotal": _num(buscar(r'S\s*U\s*B\s*T\s*O\s*T\s*A\s*L\s*\n([\d.,]+)', texto)),
            "descuentos": _num(buscar(r'T\s*O\s*T\s*A\s*L\s*D\s*E\s*S\s*C\s*U\s*E\s*N\s*T\s*O\s*S\s*\n(-?[\d.,]+)', texto)),
            "total_sin_iva": _num(buscar(r'TOTAL\s+SIN\s+IVA[^\n]*\n([\d.,]+)', texto)),
            "iva_pct": _num(buscar(r'%\s*IVA\s*\n(\d+)', texto)),
            "total_con_iva": _num(buscar(r'SUMA TOTAL\s*\n([\d.,]+)', texto)),
        }
    }

def _num(valor):
    if valor is None:
        return None
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except ValueError:
        return None

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
        print("Procesando datos...")
        return extraer_datos(texto)
    except Exception as e:
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_unlocked):
            os.remove(temp_unlocked)


# --- Ejemplo de uso ---
resultado = procesar_expediente("informe_audatex.pdf")
print(json.dumps(resultado, indent=4, ensure_ascii=False))
