"""
Arquivo: core/github_updater.py
Descrição: Gerenciador de download e verificação de atualizações no GitHub.
Este arquivo contém a classe GitHubUpdater que checa se existe uma nova versão
disponível do LogFácil diretamente do repositório no GitHub. Ele possui a lógica
para verificar atualizações comparando as versões via um arquivo JSON específico
ou consultando as Releases oficiais (via API do GitHub). Além disso, a classe é
responsável por realizar o download seguro do novo executável para um diretório
temporário e reportar o progresso do download para a interface da aplicação.
"""
import os
import tempfile
import requests
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
        headers = {'User-Agent': 'LogFacil-Updater/1.0'}
        
        # Método 1: version.json
        try:
            version_url = f"{self.raw_url}/version.json"
            response = requests.get(version_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest = data.get('version', '')
                download_url = data.get('download_url', '')
                self.release_notes = data.get('notes', '')
                
                if latest and self._is_newer(latest, self.current_version):
                    self.latest_version = latest
                    self.download_url = download_url
                    logger.info(f"Nova versão encontrada via json: {latest}")
                    return True, latest, download_url
        except Exception as e:
            logger.debug(f"version.json não encontrado ou erro na requisição: {e}")
        
        # Método 2: GitHub Releases
        try:
            releases_url = f"{self.api_url}/releases/latest"
            headers['Accept'] = 'application/vnd.github.v3+json'
            
            response = requests.get(releases_url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
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
            elif response.status_code == 404:
                logger.debug("Nenhuma release encontrada")
            else:
                logger.error(f"Erro HTTP ao verificar atualizações: {response.status_code}")
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
        """Baixa a atualização com robustez usando requests."""
        if not self.download_url:
            logger.error("URL de download não definida!")
            return None
        
        filepath = None
        try:
            temp_dir = tempfile.gettempdir()
            update_dir = os.path.join(temp_dir, "LogFacil_Update")
            os.makedirs(update_dir, exist_ok=True)
            
            filename = f"LogFacil_{self.latest_version}.exe"
            filepath = os.path.join(update_dir, filename)
            
            headers = {'User-Agent': 'LogFacil-Updater/1.0'}
            response = requests.get(self.download_url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            # Pega o tamanho de forma segura (se não existir, fica 0)
            content_length = response.headers.get('content-length')
            total_size = int(content_length) if content_length and content_length.isdigit() else 0
            
            downloaded = 0
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: # Filtra chunks keep-alive
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if progress_callback and total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            progress_callback(percent, downloaded, total_size)
                        elif progress_callback and total_size == 0:
                            progress_callback(50, downloaded, downloaded) # Progresso indeterminado mas rodando
            
            # Para requests onde content-length não veio
            if progress_callback and total_size == 0 and downloaded > 0:
                 progress_callback(100, downloaded, downloaded)
            
            # Verificar se o arquivo tem tamanho razoável (pelo menos 3 MB)
            file_size = os.path.getsize(filepath)
            if file_size < 3 * 1024 * 1024:
                logger.error(f"Arquivo baixado muito pequeno ({file_size} bytes). Possível bloqueio corporativo ou firewal.")
                try: os.remove(filepath) 
                except: pass
                return None
            
            logger.info(f"Download concluído com sucesso: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Erro pesado no download: {e}")
            if filepath and os.path.exists(filepath):
                try: os.remove(filepath)
                except: pass
            return None
