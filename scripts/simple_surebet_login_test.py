#!/usr/bin/env python3
"""
Simple test: abrir Firefox en página de login de Surebet.
Solo una pestaña, URL específica, sin complicaciones.
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    """Abrir Firefox en login de Surebet"""
    url = "https://es.surebet.com/users/sign_in"
    
    print(f"Abriendo Firefox en: {url}")
    
    with sync_playwright() as p:
        # Chromium en servidor Linux
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navegar a login
        page.goto(url)
        print(f"✅ Página cargada: {url}")
        print("Puedes hacer login manualmente...")
        print("Presiona Ctrl+C para cerrar")
        
        try:
            # Mantener abierto
            page.wait_for_timeout(300000)  # 5 minutos
        except KeyboardInterrupt:
            print("\n🔚 Cerrando navegador")
        finally:
            browser.close()

if __name__ == "__main__":
    main()
