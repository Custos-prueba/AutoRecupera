

import json
import re
import sys
from pathlib import Path

import pdfplumber


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _num(texto: str) -> float | None:
    """Convierte '1.750,35' o '242,50' a float. Devuelve None si falla."""
    if not texto:
        return None
    limpio = texto.strip().replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def _buscar(patron: str, texto: str, grupo: int = 1) -> str | None:
    m = re.search(patron, texto)
    return m.group(grupo).strip() if m else None


# ---------------------------------------------------------------------------
# Extracción por secciones
# ---------------------------------------------------------------------------

def extraer_datos_generales(texto: str) -> dict:
    """Página 3 – DATOS GENERALES y DATOS VEHÍCULO."""
    return {
        "referencia":      _buscar(r"REFERENCIA\s+([\w\-]+)", texto),
        "nr_informe":      _buscar(r"NR\s+(MWX\w+)", texto),
        "fecha_informe":   _buscar(r"NR\s+\w+\s+(\d{2}/\d{2}/\d{4})", texto),
        "fecha_siniestro": _buscar(r"FECHA DE SINIESTRO\s+(\d{2}/\d{2}/\d{4})", texto),
        "sistema_valoracion": "AUDATEX",
        "compromiso_pago": bool(re.search(r"COMPROMISO\s+S\b", texto)),
    }


def extraer_vehiculo(textos: list[str]) -> dict:
    """Extrae datos del vehículo de las primeras páginas."""
    # Concatenar páginas 1, 3 y 4 donde aparecen los datos
    texto = "\n".join(textos[:4])
    return {
        "fabricante":          _buscar(r"FABRICANTE\s+(BMW\s+\w+|[A-Z]+(?:\s+[A-Z]+)?)\s", texto),
        "modelo":              _buscar(r"MODELO\s*/\s*TIPO\s+([\w\s]+?)\s*/", texto),
        "matricula":           _buscar(r"MATRIC(?:ULA)?\s+([\w]+)", texto),
        "vin":                 _buscar(r"(?:NR CHASIS|NÚMERO CHASIS)\s+([\w]+)", texto),
        "codigo_tipo":         _buscar(r"CÓDIGO TIPO\s+([\w]+)", texto),
        "fecha_matriculacion": _buscar(r"FECHA MATRICULACIÓN\s+(\d{2}/\d{2}/\d{4})", texto),
        "kilometros":          _num(_buscar(r"KILÓMETROS\s+([\d.]+)", texto)),
        "color":               _buscar(r"(BLACK STORM MET|[A-Z ]+MET(?:ALIZADO)?)", texto),
        "acabado":             _buscar(r"BICAPA|TRICAPA|MONOCAPA", texto, 0),
        "potencia_cv":         _num(_buscar(r"(\d+)CV/", texto)),
        "potencia_kw":         _num(_buscar(r"/(\d+)KW", texto)),
        "cilindrada_cc":       _num(_buscar(r"(\d{3,4})\s*CC", texto)),
    }


def extraer_valoracion(texto: str) -> dict:
    """Páginas 3 y 6 – totales económicos."""
    return {
        "total_repuestos":  _num(_buscar(r"REPUESTOS\s+([\d.,]+)", texto)),
        "total_mo":         _num(_buscar(r"TOTAL M\.O\. CHAPA/MECÁNICA\s+([\d.,]+)", texto)),
        "subtotal":         _num(_buscar(r"SUBTOTAL\s+([\d.,]+)", texto)),
        "descuentos":       _num(_buscar(r"TOTAL DESCUENTOS\s+(-?[\d.,]+)", texto)),
        "total_sin_iva":    _num(_buscar(r"SUMA TOTAL SIN IVA\s+Euros\s+([\d.,]+)", texto)),
        "iva_pct":          _num(_buscar(r"(\d+)%\s*IVA", texto)),
        "total_con_iva":    _num(_buscar(r"SUMA TOTAL CON IVA\s+Euros\s+([\d.,]+)", texto)),
        "horas_mo":         _buscar(r"TOTAL DE HORAS DE MANO DE OBRA\s+([\d\s\w.]+?)(?:\n|$)", texto),
    }


def extraer_piezas(pdf_path: str) -> list[dict]:
    """
    Extrae la tabla PIEZAS SUSTITUIDAS usando coordenadas de columna (pdfplumber).
    Columnas aproximadas (x0):
      POS ~46 | DESCRIPCIÓN ~101 | REFERENCIA ~270 | CANTIDAD ~346 | DTO ~418 | PRECIO ~459
    """
    COL_POS   = (40,  75)
    COL_DESC  = (95, 265)
    COL_REF   = (265, 340)
    COL_CANT  = (340, 415)
    COL_DTO   = (415, 455)
    COL_PRECIO= (455, 510)

    piezas = []
    en_tabla = False

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texto_pag = page.extract_text() or ""
            if "PIEZAS SUSTITUIDAS" in texto_pag:
                en_tabla = True
            if not en_tabla:
                continue

            words = page.extract_words()
            # Agrupar palabras por línea (top redondeado a 2px)
            lineas: dict[int, list] = {}
            for w in words:
                top = round(w["top"])
                lineas.setdefault(top, []).append(w)

            for top in sorted(lineas):
                fila = lineas[top]
                # Función auxiliar: texto de palabras dentro de rango x
                def col(x0, x1):
                    return " ".join(w["text"] for w in fila if w["x0"] >= x0 and w["x1"] <= x1)

                pos = col(*COL_POS)
                if not re.match(r"^\d{4}$", pos.strip()):
                    continue  # sólo filas con posición de 4 dígitos

                desc    = col(*COL_DESC).strip()
                ref     = col(*COL_REF).strip()
                cant    = col(*COL_CANT).strip()
                dto     = col(*COL_DTO).strip()
                precio  = col(*COL_PRECIO).strip().rstrip("*").strip()

                piezas.append({
                    "pos":              pos.strip(),
                    "descripcion":      desc,
                    "referencia_pieza": ref,
                    "cantidad":         _num(cant),
                    "dto_pct":          int(dto) if dto.isdigit() else None,
                    "importe":          _num(precio),
                    "operacion":        "SUSTITUIR",
                })

            if "TOTAL PIEZAS" in texto_pag:
                break

    return piezas


def extraer_mano_obra(texto: str) -> list[dict]:
    """Páginas 4-5 – operaciones de mano de obra."""
    operaciones = []
    inicio = texto.find("OPERACIONES DE LA VALORACIÓN")
    fin    = texto.find("TOTAL M.O. CH/MEC.")
    if inicio == -1 or fin == -1:
        return operaciones

    bloque = texto[inicio:fin]

    # Patrón: referencia operación | descripción | UT | importe
    patron = re.compile(
        r"^([\w\s]+?\d{3}[).]?)\s+"   # nr operación
        r"(.+?)\s+"                    # descripción
        r"(\d+)\s+"                    # UT
        r"([\d.,]+)$",                 # importe
        re.MULTILINE
    )

    for m in patron.finditer(bloque):
        operaciones.append({
            "nr_operacion": m.group(1).strip(),
            "descripcion":  m.group(2).strip(),
            "ut":           int(m.group(3)),
            "importe":      _num(m.group(4)),
        })

    return operaciones


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def extraer_datos(ruta_pdf: str) -> dict:
    with pdfplumber.open(ruta_pdf) as pdf:
        paginas = [p.extract_text() or "" for p in pdf.pages]

    texto_completo = "\n".join(paginas)

    datos = extraer_datos_generales(texto_completo)
    datos["vehiculo"]    = extraer_vehiculo(paginas)
    datos["valoracion"]  = extraer_valoracion(texto_completo)
    datos["piezas_danadas"] = extraer_piezas(ruta_pdf)
    datos["mano_obra"]   = extraer_mano_obra(texto_completo)

    return datos


def guardar_json(datos: dict, ruta_pdf: str) -> str:
    nombre = Path(ruta_pdf).stem + ".json"
    ruta_salida = Path("/mnt/user-data/outputs") / nombre
    with open(ruta_salida, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return str(ruta_salida)


def main():
    if len(sys.argv) < 2:
        print("Uso: python autorecupera_extractor.py <ruta_pdf>")
        sys.exit(1)

    ruta_pdf = sys.argv[1]
    if not Path(ruta_pdf).exists():
        print(f"Error: no se encuentra el archivo {ruta_pdf}")
        sys.exit(1)

    print(f"Procesando: {ruta_pdf}")
    datos = extraer_datos(ruta_pdf)

    print("\n--- DATOS EXTRAÍDOS ---")
    print(json.dumps(datos, ensure_ascii=False, indent=2))

    ruta_json = guardar_json(datos, ruta_pdf)
    print(f"\nGuardado en: {ruta_json}")

    v   = datos.get("vehiculo", {})
    val = datos.get("valoracion", {})
    print("\n--- RESUMEN ---")
    print(f"Vehículo : {v.get('fabricante')} {v.get('modelo')} ({v.get('matricula')})")
    print(f"VIN      : {v.get('vin')}")
    print(f"Kms      : {v.get('kilometros')}")
    print(f"Piezas   : {len(datos.get('piezas_danadas', []))} líneas")
    print(f"Repuestos: {val.get('total_repuestos')} €")
    print(f"M.O.     : {val.get('total_mo')} €")
    print(f"Total    : {val.get('total_con_iva')} € (con IVA)")


if __name__ == "__main__":
    main()