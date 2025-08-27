#!/usr/bin/env python3
"""
Script simple para probar login en Surebet con captura de requests
Usa Chromium en servidor Linux con GUI para interacción manual
"""

import os
import sys
import time
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright, BrowserContext, Page, Request, Response


class SimplePlaywrightCapture:
    """Captura simplificada de requests sin dependencias externas"""
    
    def __init__(self, target: BrowserContext | Page, url_patterns: Optional[list[str]] = None):
        self.target = target
        self.url_patterns = url_patterns or []
        self.buffer: List[Dict[str, Any]] = []
        
    def _matches_pattern(self, url: str) -> bool:
        """Verifica si la URL coincide con algún patrón"""
        if not self.url_patterns:
            return True
        return any(re.search(pattern, url, re.IGNORECASE) for pattern in self.url_patterns)
    
    def _on_request(self, request: Request):
        """Maneja requests interceptados"""
        if self._matches_pattern(request.url):
            data = {
                "type": "request",
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "timestamp": time.time()
            }
            # Intentar extraer JSON del body
            try:
                if request.post_data:
                    data["json"] = json.loads(request.post_data)
            except (json.JSONDecodeError, TypeError):
                pass
            self.buffer.append(data)
    
    def _on_response(self, response: Response):
        """Maneja responses interceptados"""
        if self._matches_pattern(response.url):
            data = {
                "type": "response",
                "url": response.url,
                "status": response.status,
                "headers": dict(response.headers),
                "timestamp": time.time()
            }
            # Intentar extraer JSON del body
            try:
                if response.headers.get("content-type", "").startswith("application/json"):
                    data["json"] = response.json()
            except Exception:
                pass
            self.buffer.append(data)
    
    def start(self):
        """Inicia la captura de requests/responses"""
        self.target.on("request", self._on_request)
        self.target.on("response", self._on_response)
    
    def flush(self) -> List[Dict[str, Any]]:
        """Retorna y limpia el buffer de datos capturados"""
        data = self.buffer.copy()
        self.buffer.clear()
        return data


def main():
    """Abrir Chromium en login de Surebet con captura de requests"""
    url = "https://es.surebet.com/users/sign_in"
    
    # Patrones para capturar requests de Surebet
    surebet_patterns = [r"/api/", r"/valuebets", r"/surebets", r"/arbs", r"/users/"]
    
    print("=" * 60)
    print("🚀 INICIANDO TEST DE SUREBET LOGIN")
    print("=" * 60)
    print(f"📍 URL objetivo: {url}")
    print(f"🔍 Patrones de captura: {surebet_patterns}")
    print()
    
    with sync_playwright() as p:
        print("🔧 Iniciando Playwright...")
        
        # Chromium en servidor Linux con args adicionales
        print("🌐 Lanzando Chromium con argumentos para servidor Linux...")
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ]
        )
        print("✅ Chromium lanzado exitosamente")
        
        print("📄 Creando contexto de navegación...")
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        print("✅ Contexto creado")
        
        # Configurar captura de requests ANTES de crear la página
        print("🎯 Configurando captura de requests...")
        try:
            capture = SimplePlaywrightCapture(context, url_patterns=surebet_patterns)
            capture.start()
            print("✅ Captura de requests iniciada")
        except Exception as e:
            print(f"❌ Error configurando captura: {e}")
            return 1
        
        print("📱 Creando nueva página...")
        page = context.new_page()
        print("✅ Página creada")
        
        # Navegar a login con timeout largo y manejo de errores
        print(f"🚀 Navegando a: {url}")
        navigation_success = False
        
        try:
            print("   ⏳ Intentando navegación con networkidle...")
            page.goto(url, wait_until="networkidle", timeout=30000)
            print(f"   ✅ Página cargada con networkidle: {page.url}")
            navigation_success = True
        except Exception as e:
            print(f"   ❌ Error con networkidle: {type(e).__name__}: {e}")
            print("   🔄 Intentando navegación básica...")
            try:
                page.goto(url, timeout=30000)
                final_url = page.url
                print(f"   ✅ Página cargada (básica): {final_url}")
                if final_url != "about:blank":
                    navigation_success = True
                else:
                    print("   ⚠️  Página quedó en about:blank")
            except Exception as e2:
                print(f"   ❌ Error crítico: {type(e2).__name__}: {e2}")
                print(f"   📍 URL actual: {page.url}")
                print("   🔧 Manteniendo navegador abierto para diagnóstico manual...")
        
        print(f"\n📊 Estado final:")
        print(f"   URL actual: {page.url}")
        print(f"   Navegación exitosa: {navigation_success}")
        print(f"   Título: {page.title()}")
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
