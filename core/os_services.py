import sys
import os
import subprocess
import ctypes
import time
from typing import Tuple, List

from core.logger import logger
from core.config import SERVICE_COMPONENTS

def is_admin() -> bool:
    """Verifica se o processo atual possui privilégios administrativos."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        logger.warning(f"Erro ao verificar privilégios de administrador: {e}")
        return False

def run_as_admin() -> bool:
    """Reinicia o processo atual exigindo privilégios administrativos (UAC bypass/prompt)."""
    try:
        script = os.path.abspath(sys.argv[0])
        if script.endswith('.py'):
            executable = sys.executable
            params = f'"{script}"'
        else:
            executable = script
            params = ' '.join(sys.argv[1:])
        
        ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
        sys.exit(0)
    except Exception as e:
        logger.error(f"Erro ao tentar elevar privilégios: {e}")
        return False

def run_command_hidden(command: list) -> Tuple[bool, str]:
    """Executa um comando local desabilitando a janela preta do console (comum no Windows)."""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            timeout=30,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout ao executar comando: {' '.join(command)}")
        return False, "Erro: Timeout excedido"
    except Exception as e:
        logger.error(f"Erro ao executar comando invisível: {' '.join(command)} -> {e}")
        return False, str(e)

def check_admin_and_warn() -> Tuple[bool, str]:
    if os.name == "nt" and not is_admin():
        return False, "⚠ Sem privilégios de administrador"
    return True, "✓ Modo administrador"

def stop_windows_service(service_name: str) -> Tuple[bool, str]:
    is_admin_flag, admin_msg = check_admin_and_warn()
    success, output = run_command_hidden(["net", "stop", service_name])
    
    if success:
        logger.info(f"Serviço '{service_name}' parado com sucesso.")
        return True, f"Serviço '{service_name}' parado"
    else:
        output_lower = output.lower()
        if "não está iniciado" in output_lower or "not started" in output_lower:
            return True, f"Serviço '{service_name}' já estava parado"
        elif "acesso negado" in output_lower or "access denied" in output_lower:
            logger.warning(f"Acesso negado ao parar {service_name}.")
            return False, f"❌ Acesso negado! {admin_msg}"
        else:
            logger.error(f"Falha ao parar serviço {service_name}: {output}")
            return False, f"Falha ao parar: {output[:200]}"

def start_windows_service(service_name: str) -> Tuple[bool, str]:
    is_admin_flag, admin_msg = check_admin_and_warn()
    success, output = run_command_hidden(["net", "start", service_name])
    
    if success:
        logger.info(f"Serviço '{service_name}' iniciado com sucesso.")
        return True, f"Serviço '{service_name}' iniciado"
    else:
        output_lower = output.lower()
        if "já foi iniciado" in output_lower or "already been started" in output_lower:
            return True, f"Serviço '{service_name}' já estava em execução"
        elif "acesso negado" in output_lower or "access denied" in output_lower:
            logger.warning(f"Acesso negado ao iniciar {service_name}.")
            return False, f"❌ Acesso negado! {admin_msg}"
        else:
            logger.error(f"Falha ao iniciar {service_name}: {output}")
            return False, f"Falha ao iniciar: {output[:200]}"

def kill_task(task_name: str) -> Tuple[bool, str]:
    is_admin_flag, admin_msg = check_admin_and_warn()
    success, output = run_command_hidden(["taskkill", "/F", "/IM", task_name])
    
    if success:
        logger.info(f"Processo '{task_name}' morto via taskkill.")
        return True, f"✅ {task_name}: finalizado"
    else:
        output_lower = output.lower()
        if "not found" in output_lower or "não encontrado" in output_lower:
            return True, f"⚠ {task_name}: não encontrado"
        elif "acesso negado" in output_lower or "access denied" in output_lower:
            logger.warning(f"Acesso negado no kill_task para {task_name}.")
            return False, f"❌ {task_name}: acesso negado! {admin_msg}"
        else:
            logger.error(f"Falha ao matar {task_name}: {output}")
            return False, f"❌ {task_name}: erro"

def check_service_status(service_name: str) -> Tuple[bool, bool, str]:
    """Retorna: (Existe?, Rodando?, Mensagem)"""
    success, output = run_command_hidden(["sc", "query", service_name])
    if not success:
        return False, False, f"Serviço '{service_name}' não encontrado"
    
    if "RUNNING" in output:
        return True, True, f"Serviço '{service_name}' em execução"
    elif "STOPPED" in output:
        return True, False, f"Serviço '{service_name}' parado"
    else:
        return True, False, f"Serviço '{service_name}' status desconhecido"

def get_default_components(service_name: str) -> dict:
    return {"services": [f"{service_name}Service", service_name], "tasks": [f"{service_name}.exe"]}

def restart_service_components(service_name: str) -> Tuple[bool, List[str]]:
    if os.name != "nt":
        return False, ["Funcionalidade disponível apenas no Windows"]
    
    components = SERVICE_COMPONENTS.get(service_name, get_default_components(service_name))
    results = [f"🔄 Reiniciando {service_name}...", "-" * 40]
    
    is_admin_flag, admin_msg = check_admin_and_warn()
    results.append(f"🔑 Status: {admin_msg}")
    results.append("")
    
    all_success = True
    services = components.get("services", [])
    
    if services:
        results.append("📌 Parando serviços:")
        for svc in reversed(services):
            exists, running, status_msg = check_service_status(svc)
            results.append(f"  {status_msg}")
            if exists and running:
                success, msg = stop_windows_service(svc)
                results.append(f"  → {msg}")
                if not success:
                    all_success = False
    
    time.sleep(2)
    
    tasks = components.get("tasks", [])
    if tasks:
        results.append("\n📌 Finalizando processos:")
        for task in tasks:
            success, msg = kill_task(task)
            results.append(f"  {msg}")
    
    time.sleep(1)
    
    if services:
        results.append("\n📌 Iniciando serviços:")
        for svc in services:
            exists, running, status_msg = check_service_status(svc)
            if exists:
                success, msg = start_windows_service(svc)
                results.append(f"  → {msg}")
    
    results.append("")
    results.append("✅ Concluído!" if all_success else "⚠ Concluído com erros")
    return all_success, results
