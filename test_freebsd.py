#!/usr/bin/env python3
"""
Script de prueba: FreeBSD → Ollama Windows
Verifica que todo está listo para ejecutar autorecupera.py
"""

import requests
import sys
import json

OLLAMA_HOST = "http://10.68.52.11:11434"

def test_connectivity():
    """Test 1: Verificar conectividad TCP"""
    print("1️⃣  Verificando conectividad TCP...", end="", flush=True)
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        print(" ✅")
        return True
    except requests.exceptions.Timeout:
        print(" ⏱️ TIMEOUT")
        return False
    except requests.exceptions.ConnectionError as e:
        print(" ❌")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        print(f" ❌ {e}")
        return False

def test_models():
    """Test 2: Listar modelos disponibles"""
    print("2️⃣  Listando modelos...", end="", flush=True)
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            print(f" ✅ ({len(models)} modelos)")
            
            for model in models:
                name = model.get("name", "unknown")
                print(f"      • {name}")
            
            return True
        else:
            print(f" ❌ Status {response.status_code}")
            return False
    except Exception as e:
        print(f" ❌ {e}")
        return False

def test_chat():
    """Test 3: Prueba de chat simple"""
    print("3️⃣  Probando chat...", end="", flush=True)
    try:
        payload = {
            "model": "qwen2.5:14b",
            "messages": [{"role": "user", "content": "Responde solo OK"}],
            "stream": False
        }
        response = requests.post(
            f"{OLLAMA_HOST}/api/chat",
            json=payload,
            timeout=60
        )
        if response.status_code == 200:
            data = response.json()
            content = data.get("message", {}).get("content", "")
            print(f" ✅")
            print(f"      Respuesta: {content[:50]}...")
            return True
        else:
            print(f" ❌ Status {response.status_code}")
            return False
    except Exception as e:
        print(f" ❌ {e}")
        return False

def test_vision():
    """Test 4: Verificar modelo vision"""
    print("4️⃣  Verificando modelo vision...", end="", flush=True)
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        data = response.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        
        if any("qwen2.5vl" in m for m in models):
            print(" ✅")
            return True
        else:
            print(" ⚠️ NO ENCONTRADO")
            print("      Necesitas: ollama pull qwen2.5vl:7b")
            return False
    except Exception as e:
        print(f" ❌ {e}")
        return False

def main():
    print("")
    print("=" * 60)
    print("  PRUEBA: FreeBSD → Ollama Windows")
    print("=" * 60)
    print(f"\n📍 Ollama Host: {OLLAMA_HOST}\n")
    
    results = []
    
    # Test 1
    if not test_connectivity():
        print("\n❌ No hay conectividad. Abortando.")
        print("\nVerifica:")
        print("  • ¿Ollama está corriendo en Windows?")
        print("  • ¿Firewall abierto en puerto 11434?")
        print("  • ¿Conectividad entre máquinas? (ping 10.68.52.11)")
        return 1
    
    results.append(True)
    
    # Test 2
    results.append(test_models())
    
    # Test 3
    results.append(test_chat())
    
    # Test 4
    results.append(test_vision())
    
    print()
    print("=" * 60)
    
    if all(results):
        print("  ✅ TODOS LOS TESTS PASARON")
        print("=" * 60)
        print("\n🚀 Listo para ejecutar autorecupera.py\n")
        print("Comando:")
        print(f"  export OLLAMA_HOST='{OLLAMA_HOST}'")
        print(f"  python3 autorecupera.py informe.pdf\n")
        return 0
    else:
        print("  ⚠️ ALGUNOS TESTS FALLARON")
        print("=" * 60)
        print("\nCorrige los errores arriba antes de continuar.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
