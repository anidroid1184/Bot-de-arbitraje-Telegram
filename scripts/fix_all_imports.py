#!/usr/bin/env python3
"""
Script para corregir automáticamente todos los imports relativos problemáticos.
"""
import os
import re
from pathlib import Path

def fix_relative_imports():
    """Corrige todos los imports relativos en el proyecto."""
    src_path = Path(__file__).parent.parent / "src"
    
    # Mapeo de imports problemáticos a sus reemplazos
    import_fixes = {
        r'from \.\.utils\.logger import get_module_logger': 'import structlog',
        r'from \.\.config\.config import get_config': 'from config.config import get_config',
        r'from \.\.config import get_config': 'from config.config import get_config',
        r'from \.\.browser\.playwright_manager import PlaywrightManager': 'from browser.playwright_manager import PlaywrightManager',
        r'from \.\.browser\.tab_manager import TabManager': 'from browser.tab_manager import TabManager',
        r'from \.\.browser\.auth_manager import AuthManager': 'from browser.auth_manager import AuthManager',
        r'from \.\.network\.playwright_capture import PlaywrightCapture': 'from network.playwright_capture import PlaywrightCapture',
        r'from \.\.parsers\.betburger_html import BetburgerHtmlParser': 'from parsers.betburger_html import BetburgerHtmlParser',
        r'from \.\.parsers\.surebet_html import SurebetHtmlParser': 'from parsers.surebet_html import SurebetHtmlParser',
        r'from \.\.processing\.router import ProcessingRouter': 'from processing.router import ProcessingRouter',
        r'from \.\.scrapers\.surebet import SurebetScraper': 'from scrapers.surebet import SurebetScraper',
        r'from \.\.snapshots\.snapshot_manager import SnapshotManager': 'from snapshots.snapshot_manager import SnapshotManager',
        r'from \.\.utils\.command_controller import CommandController': 'from utils.command_controller import CommandController',
        r'from \.\.ocr\.ocr_utils import OCRUtils': 'from ocr.ocr_utils import OCRUtils',
        r'logger = get_module_logger\(__name__\)': 'logger = structlog.get_logger(__name__)',
    }
    
    files_fixed = 0
    
    # Buscar todos los archivos .py en src/
    for py_file in src_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Aplicar todas las correcciones
            for pattern, replacement in import_fixes.items():
                content = re.sub(pattern, replacement, content)
            
            # Si hubo cambios, escribir el archivo
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Fixed: {py_file.relative_to(src_path)}")
                files_fixed += 1
                
        except Exception as e:
            print(f"❌ Error fixing {py_file}: {e}")
    
    print(f"\n🎯 Fixed {files_fixed} files")

if __name__ == "__main__":
    fix_relative_imports()
