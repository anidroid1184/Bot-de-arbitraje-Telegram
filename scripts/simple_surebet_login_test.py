#!/usr/bin/env python3
"""
Simple test: abrir Chromium en página de login de Surebet con captura de requests.
Solo una pestaña, URL específica, interceptando requests de API.
"""
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# Bootstrap path
_this_dir = Path(__file__).parent
_project_root = _this_dir.parent
sys.path.insert(0, str(_project_root))

from src.network.playwright_capture import PlaywrightCapture

def main():
    """Abrir Chromium en login de Surebet con captura de requests"""
    url = "https://es.surebet.com/users/sign_in"
    
    # Patrones para capturar requests de Surebet
    surebet_patterns = [r"/api/", r"/valuebets", r"/surebets", r"/arbs", r"/users/"]
    
    print(f"Abriendo Chromium en: {url}")
    print("🔍 Capturando requests de Surebet...")
    
    with sync_playwright() as p:
        # Chromium en servidor Linux
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # Configurar captura de requests ANTES de crear la página
        capture = PlaywrightCapture(context, url_patterns=surebet_patterns)
        capture.start()
        
        page = context.new_page()
        
        # Navegar a login
        page.goto(url)
        print(f"✅ Página cargada: {url}")
        print("Puedes hacer login manualmente y navegar...")
        print("Los requests se mostrarán en tiempo real")
        print("Presiona Ctrl+C para cerrar\n")
        
        try:
            # Loop para mostrar requests capturados
            while True:
                time.sleep(2)
                data = capture.flush()
                for rec in data:
                    rtype = rec.get("type", "?")
                    url_req = rec.get("url", "")
                    method = rec.get("method", "")
                    status = rec.get("status", "")
                    
                    if rtype == "request":
                        print(f"[REQ] {method} {url_req}")
                        if rec.get("json"):
                            print(f"      JSON: {rec['json']}")
                    elif rtype == "response":
                        print(f"[RES] {status} {url_req}")
                        if rec.get("json"):
                            print(f"      JSON: {rec['json']}")
                        
        except KeyboardInterrupt:
            print("\n🔚 Cerrando navegador")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
