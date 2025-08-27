#!/usr/bin/env python3
"""Simple Surebet test - open GUI and capture network requests.

Usage:
  python scripts/simple_surebet_test.py
"""
import os
import sys
import time
from pathlib import Path

# Bootstrap path
_this_dir = Path(__file__).parent
_project_root = _this_dir.parent
sys.path.insert(0, str(_project_root))

from playwright.sync_api import sync_playwright
from src.network.playwright_capture import PlaywrightCapture

def main():
    # Force GUI and no resource blocking
    url = "https://es.surebet.com/users/sign_in"
    
    with sync_playwright() as p:
        # Launch Firefox headless (Linux server)
        browser = p.firefox.launch(headless=True)
        context = browser.new_context()
        
        # Set longer timeouts
        context.set_default_navigation_timeout(30000)
        context.set_default_timeout(30000)
        
        # Setup network capture for Surebet patterns
        capture = PlaywrightCapture(context, url_patterns=[
            r"/api/", r"/valuebets", r"/surebets", r"/arbs", r"/users/"
        ])
        capture.start()
        
        # Open page
        page = context.new_page()
        print(f"Navegando a: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        
        print("✅ Página cargada en modo headless")
        print("🔍 Capturando requests de Surebet...")
        print("Presiona Ctrl+C para salir\n")
        
        # Simulate basic navigation to trigger requests
        try:
            # Try to get initial page content
            content = page.content()
            print(f"📄 Página cargada: {len(content)} chars")
            
            # Try to navigate to surebets page
            try:
                surebets_url = "https://es.surebet.com/surebets"
                print(f"🔄 Navegando a: {surebets_url}")
                page.goto(surebets_url, wait_until="networkidle", timeout=30000)
                print("✅ Navegación a /surebets completada")
            except Exception as e:
                print(f"⚠️ Error navegando a /surebets: {e}")
            
            # Keep alive and capture for 30 seconds
            start_time = time.time()
            while time.time() - start_time < 30:
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
                        
        except KeyboardInterrupt:
            print("\n🔍 Captura finalizada")
            
        finally:
            browser.close()

if __name__ == "__main__":
    main()
