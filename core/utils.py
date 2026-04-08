import os
from typing import Dict, Tuple

from core.logger import logger
from core.config import LOG_EXTENSIONS, ENCODINGS

def service_from_path(path: str) -> str:
    parts = os.path.normpath(path).split(os.sep)
    for i, p in enumerate(parts):
        if p.lower() == "log" and i + 1 < len(parts):
            return parts[i + 1]
    return "?"

def open_text_auto(path: str):
    """Tenta abrir um arquivo como texto usando as codificações conhecidas, fall back para binário."""
    for enc in ENCODINGS:
        try:
            return open(path, "r", encoding=enc, errors="replace"), True
        except OSError:
            pass # Ignora erro de SO (ex. arquivo lockado) e tenta outro
    try:
        return open(path, "rb", buffering=0), False
    except Exception as e:
        logger.error(f"Falha total ao abrir arquivo '{path}': {e}")
        raise

def seek_tail(fobj, max_bytes: int):
    """Vai pro final do arquivo menos `max_bytes` e garante uma nova linha."""
    try:
        fobj.seek(0, os.SEEK_END)
        size = fobj.tell()
        start = max(size - max_bytes, 0)
        fobj.seek(start, os.SEEK_SET)
        if start > 0:
            fobj.readline()
    except Exception as e:
        logger.warning(f"Erro ao fazer seek_tail no objeto: {e}")

def scan_log_files(root: str) -> Dict[str, Tuple[str, float]]:
    files_by_service = {}
    if not os.path.isdir(root):
        return files_by_service
    
    root_name = os.path.basename(os.path.normpath(root)).lower()
    scan_root = root if root_name == "log" else os.path.join(root, "LOG")
    
    if not os.path.isdir(scan_root):
        return files_by_service
    
    try:
        service_folders = [f for f in os.listdir(scan_root) if os.path.isdir(os.path.join(scan_root, f))]
        
        for service in service_folders:
            service_dir = os.path.join(scan_root, service)
            latest_file = None
            latest_mtime = 0
            
            for root_dir, dirs, files in os.walk(service_dir):
                for file in files:
                    if file.lower().endswith(LOG_EXTENSIONS):
                        filepath = os.path.join(root_dir, file)
                        try:
                            mtime = os.path.getmtime(filepath)
                            if mtime > latest_mtime:
                                latest_mtime = mtime
                                latest_file = filepath
                        except OSError:
                            continue
            
            if latest_file:
                files_by_service[service] = (latest_file, latest_mtime)
    except Exception as e:
        logger.error(f"Erro ao scannear pasta raiz {scan_root}: {e}")
    
    return files_by_service

def find_latest_by_service(root: str) -> Dict[str, str]:
    latest = {}
    files_by_service = scan_log_files(root)
    for svc, (path, mtime) in files_by_service.items():
        latest[svc] = path
    return latest
