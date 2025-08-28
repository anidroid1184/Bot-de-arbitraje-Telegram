#!/usr/bin/env python3
"""
Debug script para verificar imports y dependencias del proyecto.
"""
import sys
import os
from pathlib import Path

def test_python_path():
    """Test que el sys.path esté configurado correctamente."""
    src_path = str(Path(__file__).parent.parent / "src")
    
    print(f"🔍 Directorio src: {src_path}")
    print(f"🔍 Existe directorio src: {os.path.exists(src_path)}")
    
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        print(f"✅ Agregado {src_path} a sys.path")
    else:
        print(f"✅ {src_path} ya está en sys.path")
    
    # Listar contenido de src/
    if os.path.exists(src_path):
        subdirs = [d for d in os.listdir(src_path) if os.path.isdir(os.path.join(src_path, d))]
        print(f"📁 Subdirectorios en src/: {subdirs}")
    
    return src_path

def test_individual_modules():
    """Test imports individuales de cada módulo."""
    modules_to_test = [
        ("structlog", "structlog"),
        ("aiohttp", "aiohttp"),
        ("playwright.sync_api", "playwright"),
        ("config.settings", "config/settings.py"),
        ("processors.arbitrage_data", "processors/arbitrage_data.py"),
        ("notifications.telegram_sender", "notifications/telegram_sender.py"),
        ("pipeline.realtime_processor", "pipeline/realtime_processor.py"),
        ("browser.playwright_manager", "browser/playwright_manager.py"),
        ("network.playwright_capture", "network/playwright_capture.py"),
    ]
    
    results = {}
    
    for module_name, file_path in modules_to_test:
        try:
            __import__(module_name)
            print(f"✅ {module_name}")
            results[module_name] = True
        except ImportError as e:
            print(f"❌ {module_name}: {e}")
            results[module_name] = False
        except Exception as e:
            print(f"⚠️ {module_name}: {e}")
            results[module_name] = False
    
    return results

def check_dependencies():
    """Verificar dependencias críticas."""
    critical_deps = [
        "structlog",
        "aiohttp", 
        "playwright",
        "dotenv",
        "yaml"
    ]
    
    missing = []
    
    for dep in critical_deps:
        try:
            if dep == "yaml":
                import yaml
            elif dep == "dotenv":
                import dotenv
            else:
                __import__(dep)
            print(f"✅ {dep} instalado")
        except ImportError:
            print(f"❌ {dep} NO instalado")
            missing.append(dep)
    
    return missing

def main():
    """Main debug function."""
    print("🚀 Debug de imports y dependencias\n")
    
    # Test 1: Python path
    print("=== 1. Python Path ===")
    src_path = test_python_path()
    print()
    
    # Test 2: Dependencias externas
    print("=== 2. Dependencias Externas ===")
    missing = check_dependencies()
    print()
    
    # Test 3: Módulos del proyecto
    print("=== 3. Módulos del Proyecto ===")
    results = test_individual_modules()
    print()
    
    # Resumen
    print("=== RESUMEN ===")
    if missing:
        print(f"❌ Dependencias faltantes: {missing}")
        print("   Ejecuta: pip install -r requirements.txt")
    else:
        print("✅ Todas las dependencias externas instaladas")
    
    failed_modules = [mod for mod, success in results.items() if not success]
    if failed_modules:
        print(f"❌ Módulos del proyecto con errores: {failed_modules}")
    else:
        print("✅ Todos los módulos del proyecto importan correctamente")
    
    return 0 if not missing and not failed_modules else 1

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
