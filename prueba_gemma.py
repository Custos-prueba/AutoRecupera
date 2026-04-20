# import fitz  # PyMuPDF
# import pikepdf
# import google.generativeai as genai
# import json
# import os

# # ==========================================
# # CONFIGURACIÓN
# # ==========================================
# GENAI_API_KEY = "TU_API_KEY_AQUI"
# genai.configure(api_key=GENAI_API_KEY)

# # Configuramos el modelo multimodal (Gemini/Gemma Vision)
# model = genai.GenerativeModel('gemini-1.5-flash') # O la versión de Gemma multimodal disponible

# def unlock_pdf(input_path, output_path, password):
#     """Desbloquea un PDF si tiene contraseña."""
#     try:
#         with pikepdf.open(input_path, password=password) as pdf:
#             pdf.save(output_path)
#             return True
#     except Exception as e:
#         print(f"Error al desbloquear PDF: {e}")
#         return False

# def pdf_to_images(pdf_path):
#     """Convierte cada página del PDF en una imagen (bytes)."""
#     doc = fitz.open(pdf_path)
#     images = []
#     for page_num in range(len(doc)):
#         page = doc.load_page(page_num)
#         pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # Aumentamos resolución (x2)
#         img_bytes = pix.tobytes("png")
#         images.append({"mime_type": "image/png", "data": img_bytes})
#     doc.close()
#     return images

# def extract_data_with_ai(images):
#     """Envía las imágenes a la IA y solicita un JSON estructurado."""
    
#     prompt = """
#     Actúa como un experto en peritajes de vehículos. Analiza las imágenes de este informe de Audatex 
#     y extrae la información en formato JSON estrictamente. 
    
#     Sigue este esquema:
#     {
#       "vehiculo": {
#         "referencia": "Número de referencia del expediente",
#         "marca": "Fabricante",
#         "modelo": "Modelo y Tipo",
#         "matricula": "Matrícula",
#         "bastidor": "Número de chasis/VIN",
#         "km": "Kilometraje",
#         "fecha_matriculacion": "Fecha de primera matriculación"
#       },
#       "valoracion": {
#         "subtotal_piezas": "Solo el número (float)",
#         "total_mano_obra": "Solo el número (float)",
#         "total_sin_iva": "Solo el número (float)",
#         "total_con_iva": "Solo el número (float)"
#       },
#       "daños_principales": [
#         {"pieza": "Nombre de la pieza", "precio": 0.0, "referencia": "Código de referencia"}
#       ]
#     }
#     Si un dato no existe, pon null. No escribas texto fuera del JSON.
#     """
    
#     # Enviamos el prompt y la lista de imágenes
#     response = model.generate_content([prompt, *images])
    
#     # Limpiamos la respuesta para asegurarnos de que sea JSON válido
#     text_response = response.text.replace('```json', '').replace('```', '').strip()
#     return json.loads(text_response)

# # ==========================================
# # FLUJO PRINCIPAL (EJECUCIÓN)
# # ==========================================
# def procesar_expediente(archivo_pdf, password=None):
#     temp_unlocked = "temp_unlocked.pdf"
    
#     # 1. Gestión de contraseña
#     if password:
#         if not unlock_pdf(archivo_pdf, temp_unlocked, password):
#             return {"error": "No se pudo desbloquear el PDF"}
#         path_to_process = temp_unlocked
#     else:
#         path_to_process = archivo_pdf

#     try:
#         # 2. Conversión a imágenes (soporta nativos y escaneados)
#         print("Convirtiendo PDF a imágenes...")
#         images = pdf_to_images(path_to_process)
        
#         # 3. Extracción con IA
#         print("Analizando con Gemma/Gemini...")
#         data = extract_data_with_ai(images)
        
#         return data
#     except Exception as e:
#         return {"error": str(e)}
#     finally:
#         if os.path.exists(temp_unlocked):
#             os.remove(temp_unlocked)

# # --- Ejemplo de uso ---
# resultado = procesar_expediente("informe_audatex.pdf", password="clave123")
# print(json.dumps(resultado, indent=4, ensure_ascii=False))