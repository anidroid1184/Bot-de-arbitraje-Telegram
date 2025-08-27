#!/usr/bin/env python3
"""
Script para corregir automáticamente TODOS los imports problemáticos en el proyecto.
"""
import os
import re
from pathlib import Path

def fix_all_imports():
    """Corrige sistemáticamente todos los imports problemáticos."""
    src_path = Path(__file__).parent.parent / "src"
    
    # Patrones de corrección más completos
    import_fixes = [
        # Imports relativos con ..
        (r'from \.\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*) import ([a-zA-Z_][a-zA-Z0-9_]*)', r'from \1 import \2'),
        
        # Imports con src. explícito
        (r'from src\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*) import ([a-zA-Z_][a-zA-Z0-9_]*)', r'from \1 import \2'),
        (r'import src\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', r'import \1'),
        
        # Logger específico
        (r'from \.\.utils\.logger import get_module_logger', 'import structlog'),
        (r'from src\.utils\.logger import get_module_logger', 'import structlog'),
        (r'from utils\.logger import get_module_logger', 'import structlog'),
        (r'logger = get_module_logger\(__name__\)', 'logger = structlog.get_logger(__name__)'),
        
        # Config específico
        (r'from \.\.config\.config import get_config', 'from config.config import get_config'),
        (r'from src\.config\.config import get_config', 'from config.config import get_config'),
        (r'from \.\.config import get_config', 'from config.config import get_config'),
        (r'from src\.config import get_config', 'from config.config import get_config'),
    ]
    
    files_fixed = 0
    total_fixes = 0
    
    # Buscar todos los archivos .py en src/
    for py_file in src_path.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            file_fixes = 0
            
            # Aplicar todas las correcciones
            for pattern, replacement in import_fixes:
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    file_fixes += 1
                    total_fixes += 1
                content = new_content
            
            # Si hubo cambios, escribir el archivo
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Fixed {file_fixes} imports in: {py_file.relative_to(src_path)}")
                files_fixed += 1
                
        except Exception as e:
            print(f"❌ Error fixing {py_file}: {e}")
    
    print(f"\n🎯 Fixed {total_fixes} imports in {files_fixed} files")

if __name__ == "__main__":
    fix_all_imports()
