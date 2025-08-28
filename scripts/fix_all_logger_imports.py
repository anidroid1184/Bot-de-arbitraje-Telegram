#!/usr/bin/env python3
"""
Script para corregir TODOS los imports de get_module_logger en el proyecto.
El problema raíz: muchos archivos importan get_module_logger pero no pueden encontrarlo.
"""
import os
import re
from pathlib import Path

def fix_all_logger_imports():
    """Corrige sistemáticamente todos los imports de get_module_logger."""
    src_path = Path(__file__).parent.parent / "src"
    
    # Patrones de corrección para logger
    logger_fixes = [
        # Imports relativos de logger
        (r'from \.\.utils\.logger import get_module_logger', 'from utils.logger import get_module_logger'),
        (r'from \.utils\.logger import get_module_logger', 'from utils.logger import get_module_logger'),
        
        # Imports absolutos con src.
        (r'from src\.utils\.logger import get_module_logger', 'from utils.logger import get_module_logger'),
        
        # Imports directos que pueden fallar
        (r'from utils\.logger import get_module_logger', 'import structlog\n\ndef get_module_logger(name):\n    return structlog.get_logger(name)'),
    ]
    
    files_fixed = 0
    total_fixes = 0
    
    # Buscar todos los archivos .py en src/ y scripts/
    for search_path in [src_path, src_path.parent / "scripts"]:
        for py_file in search_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
                
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                file_fixes = 0
                
                # Solo procesar archivos que usan get_module_logger
                if 'get_module_logger' in content:
                    # Estrategia simple: reemplazar con structlog directo
                    if 'from utils.logger import get_module_logger' in content:
                        content = content.replace(
                            'from utils.logger import get_module_logger',
                            'import structlog'
                        )
                        file_fixes += 1
                    
                    if 'from ..utils.logger import get_module_logger' in content:
                        content = content.replace(
                            'from ..utils.logger import get_module_logger',
                            'import structlog'
                        )
                        file_fixes += 1
                    
                    if 'from .logger import get_module_logger' in content:
                        content = content.replace(
                            'from .logger import get_module_logger',
                            'import structlog'
                        )
                        file_fixes += 1
                    
                    if 'from src.utils.logger import get_module_logger' in content:
                        content = content.replace(
                            'from src.utils.logger import get_module_logger',
                            'import structlog'
                        )
                        file_fixes += 1
                    
                    # Reemplazar llamadas a get_module_logger
                    content = re.sub(
                        r'logger = get_module_logger\("([^"]+)"\)',
                        r'logger = structlog.get_logger("\1")',
                        content
                    )
                    content = re.sub(
                        r'logger = get_module_logger\(__name__\)',
                        r'logger = structlog.get_logger(__name__)',
                        content
                    )
                    content = re.sub(
                        r'get_module_logger\("([^"]+)"\)',
                        r'structlog.get_logger("\1")',
                        content
                    )
                    
                    if content != original_content:
                        file_fixes += 1
                
                # Si hubo cambios, escribir el archivo
                if content != original_content:
                    with open(py_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Fixed logger imports in: {py_file.relative_to(src_path.parent)}")
                    files_fixed += 1
                    total_fixes += file_fixes
                    
            except Exception as e:
                print(f"❌ Error fixing {py_file}: {e}")
    
    print(f"\n🎯 Fixed logger imports in {files_fixed} files")

if __name__ == "__main__":
    fix_all_logger_imports()
