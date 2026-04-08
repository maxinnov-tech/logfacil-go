import os

# ============================== CONFIGURAÇÃO DO GITHUB ==============================
GITHUB_REPO = "ejcastro1090/LogFacil"
GITHUB_BRANCH = "main"
CURRENT_VERSION = "1.1.8"  # Versão atual do programa
VERSION = CURRENT_VERSION

# ============================== CONFIGURAÇÕES GERAIS ==============================
DEFAULT_ROOT = r"C:\Quality\LOG" if os.name == "nt" else os.path.expanduser("~/Quality/LOG")
SCAN_INTERVAL_SEC = 1.5
TAIL_POLL_INTERVAL_SEC = 0.25
MAX_START_BYTES = 128 * 1024
MAX_VIEW_LINES = 8000
TRIM_BATCH = 600
PAUSED_BUFFER_MAX = 4000

ENCODINGS = ("cp1252", "latin-1", "utf-8")
LOG_EXTENSIONS = ('.log', '.txt', '.out', '.err', '.trace', '.debug')

SERVICE_COMPONENTS = {
    "Integra": {"tasks": ["IntegraWebService.exe"]},
    "PulserWeb": {"tasks": ["PulserWeb.exe"]},
    "webPostoFiscalServer": {"tasks": ["webPostoFiscalServer.exe"]},
    "webPostoLeituraAutomaçao": {"tasks": ["webPostoLeituraAutomacao.exe"]},
    "webPostoPayServer": {"tasks": ["webPostoPaySW.exe"]},
    "webPostoPremmialntegracao": {"tasks": ["webPostoPremiumIntegracao.exe"]},
}
