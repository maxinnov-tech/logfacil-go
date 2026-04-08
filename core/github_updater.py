import os
import json
import tempfile
import urllib.request
import urllib.error
from typing import Optional, Tuple

from core.logger import logger

class GitHubUpdater:
    """Sistema de atualização automática via GitHub."""
    
    def __init__(self, repo: str, current_version: str, branch: str = "main"):
        self.repo = repo
        self.current_version = current_version
        self.branch = branch
        self.api_url = f"https://api.github.com/repos/{repo}"
        self.raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}"
        self.latest_version = None
        self.download_url = None
        self.release_notes = ""
    
    def check_for_updates(self) -> Tuple[bool, str, Optional[str]]:
        """Verifica se há atualizações disponíveis."""
        logger.info(f"Verificando atualizações: Repo={self.repo}, Versão Atual={self.current_version}")
        
        # Método 1: version.json
        try:
            version_url = f"{self.raw_url}/version.json"
            req = urllib.request.Request(version_url)
            req.add_header('User-Agent', 'LogFacil-Updater/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            latest = data.get('version', '')
            download_url = data.get('download_url', '')
            self.release_notes = data.get('notes', '')
            
            if latest and self._is_newer(latest, self.current_version):
                self.latest_version = latest
                self.download_url = download_url
                logger.info(f"Nova versão encontrada via json: {latest}")
                return True, latest, download_url
        except Exception as e:
            logger.debug(f"version.json não encontrado ou inválido: {e}")
        
        # Método 2: GitHub Releases
        try:
            releases_url = f"{self.api_url}/releases/latest"
            req = urllib.request.Request(releases_url)
            req.add_header('Accept', 'application/vnd.github.v3+json')
            req.add_header('User-Agent', 'LogFacil-Updater/1.0')
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            latest = data.get('tag_name', '').lstrip('v')
            self.release_notes = data.get('body', '')
            
            assets = data.get('assets', [])
            for asset in assets:
                name = asset.get('name', '').lower()
                if name.endswith('.exe'):
                    self.download_url = asset.get('browser_download_url')
                    break
            
            if latest and self._is_newer(latest, self.current_version):
                self.latest_version = latest
                logger.info(f"Nova versão encontrada via GitHub Releases: {latest}")
                return True, latest, self.download_url
        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.debug("Nenhuma release encontrada")
            else:
                logger.error(f"Erro HTTP ao verificar atualizações: {e.code}")
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações: {e}")
        
        return False, self.current_version, None
    
    def _is_newer(self, latest: str, current: str) -> bool:
        """Compara versões."""
        try:
            def parse(v):
                import re
                v = v.lower().strip().lstrip('v')
                nums = re.findall(r'\d+', v)
                return [int(x) for x in nums]
            
            latest_parts = parse(latest)
            current_parts = parse(current)
            
            while len(latest_parts) < 3:
                latest_parts.append(0)
            while len(current_parts) < 3:
                current_parts.append(0)
            
            for l, c in zip(latest_parts, current_parts):
                if l > c:
                    return True
                elif l < c:
                    return False
            return False
        except Exception:
            return latest != current
    
    def download_update(self, progress_callback=None) -> Optional[str]:
        """Baixa a atualização."""
        if not self.download_url:
            logger.error("URL de download não definida!")
            return None
        
        try:
            temp_dir = tempfile.gettempdir()
            update_dir = os.path.join(temp_dir, "LogFacil_Update")
            os.makedirs(update_dir, exist_ok=True)
            
            filename = f"LogFacil_{self.latest_version}.exe"
            filepath = os.path.join(update_dir, filename)
            
            req = urllib.request.Request(self.download_url)
            req.add_header('User-Agent', 'LogFacil-Updater/1.0')
            
            with urllib.request.urlopen(req, timeout=120) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(percent, downloaded, total_size)
            
            # Verificar se o arquivo tem tamanho mínimo (pelo menos 5 MB para um executável)
            file_size = os.path.getsize(filepath)
            if file_size < 5 * 1024 * 1024:
                logger.error(f"Arquivo baixado muito pequeno ({file_size} bytes)")
                os.remove(filepath)
                return None
            
            logger.info(f"Download concluído: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erro no download: {e}")
            return None
