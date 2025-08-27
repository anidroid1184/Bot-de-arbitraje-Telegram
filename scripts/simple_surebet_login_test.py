#!/usr/bin/env python3
"""Smoke test para Surebet: interceptar requests usando lógica del smoke test existente"""

import os
import re
import sys
import time
from typing import Optional

# Bootstrap sys.path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_this_dir, os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from src.browser.playwright_manager import PlaywrightManager
from src.network.playwright_capture import PlaywrightCapture
from src.config.settings import ConfigManager
from src.utils.logger import get_module_logger

logger = get_module_logger("surebet_smoke")


def main() -> int:
    """Smoke test solo para Surebet con captura de requests"""
    
    # URLs de Surebet
    sb_base = os.environ.get("SUREBET_BASE_URL", "https://es.surebet.com").rstrip("/")
    sb_login_url = os.environ.get("SUREBET_LOGIN_URL", f"{sb_base}/users/sign_in")
    sb_start_url = os.environ.get("SUREBET_START_URL", f"{sb_base}/valuebets")
    
    # Patrones para capturar requests de Surebet
    sb_pattern_env = os.environ.get("SUREBET_PATTERNS", "").strip()
    sb_patterns = [p for p in re.split(r"[,|]", sb_pattern_env) if p] if sb_pattern_env else [r"/valuebets", r"/api/", r"/arbs", r"/surebets", r"/users/"]
    
    # Configuración
    engine = (os.environ.get("PLAYWRIGHT_ENGINE") or os.environ.get("BROWSER") or "chromium").lower()
    per_tab = False  # Forzar contexto compartido para una sola tab
    surebet_tabs = 1  # Solo una tab
    
    print("=" * 60)
    print("🎯 SUREBET SMOKE TEST - INTERCEPTANDO REQUESTS")
    print("=" * 60)
    print(f"🌐 Login URL: {sb_login_url}")
    print(f"🏠 Start URL: {sb_start_url}")
    print(f"🔍 Patrones: {sb_patterns}")
    print(f"🔧 Engine: {engine}")
    print(f"📑 Tabs: {surebet_tabs}")
    print(f"🔄 Per-tab rotation: {per_tab}")
    print()
    
    # Configurar manager
    config = ConfigManager()
    pm = PlaywrightManager(config.bot)
    captures = []
    
    try:
        print("🚀 Iniciando Playwright Manager...")
        pm.start()
        print("✅ Manager iniciado")
        
        if per_tab:
            print(f"📑 Abriendo {surebet_tabs} tabs con rotación de contexto...")
            pages = pm.open_tabs_with_context_rotation(sb_start_url, count=surebet_tabs)
            print(f"✅ {len(pages)} tabs abiertas")
            
            # Captura por contexto rotado
            for idx, ctx in enumerate(pm.rotated_contexts()):
                print(f"🎯 Configurando captura para contexto {idx}...")
                cap = PlaywrightCapture(ctx, url_patterns=sb_patterns)
                cap.start()
                captures.append(cap)
                print(f"✅ Captura {idx} iniciada")
        else:
            print("🎯 Configurando captura en contexto compartido...")
            assert pm.context is not None
            cap = PlaywrightCapture(pm.context, url_patterns=sb_patterns)
            cap.start()
            captures.append(cap)
            print("✅ Captura iniciada")
            
            print(f"📑 Abriendo {surebet_tabs} tabs...")
            pages = pm.open_tabs(sb_start_url, count=surebet_tabs)
            print(f"✅ {len(pages)} tabs abiertas")
        
        print("\n🔍 INTERCEPTANDO REQUESTS EN TIEMPO REAL")
        print("=" * 50)
        print("Navega manualmente, haz login, usa filtros...")
        print("Los requests se mostrarán automáticamente")
        print("Presiona Ctrl+C para salir\n")
        
        # Loop principal de captura (igual que Betburger smoke test)
        t0 = time.time()
        last_summary = t0
        total_matched = total_req = total_res = 0
        seen_filters = set()
        
        try:
            while True:
                # Procesar capturas (solo una captura ya que es una tab)
                for cap in captures:
                    data = cap.flush()
                    for rec in data:
                        rtype = rec.get("type")
                        url = rec.get("url")
                        if not url:
                            continue
                        total_matched += 1
                        
                        if rtype == "request":
                            total_req += 1
                            method = rec.get("method", "?")
                            has_json = isinstance(rec.get("json"), dict)
                            logger.info("[capture] request", method=method, url=url, json=has_json)
                            if has_json:
                                j = rec["json"]
                                # Buscar filter_id en requests de Surebet
                                fid = j.get("filter_id") or j.get("filterId") or j.get("id")
                                if isinstance(fid, (int, str)) and fid not in seen_filters:
                                    seen_filters.add(fid)
                                    logger.info("Detected Surebet filter_id", filter_id=fid, json_keys=list(j.keys()))
                        elif rtype == "response":
                            total_res += 1
                            status = rec.get("status")
                            logger.info("[capture] response", status=status, url=url)
                
                # Resumen periódico cada ~10s
                now = time.time()
                if now - last_summary >= 10:
                    logger.info("Capture summary", matched=total_matched, requests=total_req, responses=total_res, elapsed=int(now - t0))
                    last_summary = now
                time.sleep(1.0)
                                
        except KeyboardInterrupt:
            print("\n🔚 Cerrando smoke test...")
        
        # Resumen final
        logger.info("Capture finished", matched=total_matched, requests=total_req, responses=total_res, duration=int(time.time() - t0))
        if total_matched == 0:
            logger.warning("No Surebet traffic matched. Try logging in and using filters.")
        
        # Mantener terminal abierta opcionalmente
        if os.environ.get("SMOKE_HOLD", "0").lower() in ("1", "true", "yes", "on"):
            try:
                input("[SMOKE_HOLD] Presiona Enter para salir...")
            except Exception:
                pass
            
    except Exception as e:
        logger.error("Error en smoke test", error=str(e))
        return 1
    finally:
        pm.close()
        print("✅ Playwright Manager cerrado")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
