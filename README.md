# 📋 LogFacil – Sistema Inteligente de Consulta de Logs para WebPosto

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![Frontend](https://img.shields.io/badge/frontend-Vue.js-green)](https://vuejs.org)
[![Backend](https://img.shields.io/badge/backend-FastAPI-red)](https://fastapi.tiangolo.com)
[![Download EXE](https://img.shields.io/badge/download-latest%20release-brightgreen)](https://github.com/ejcastro1090/logfacil/releases/latest)

**LogFacil** é um sistema web desenvolvido para o **WebPosto** que revoluciona a consulta de logs.  
Ele **coleta logs automaticamente** de todos os componentes (PDVs, servidores de pagamento, bombas, etc.), eliminando a necessidade de acessar pastas manualmente ou usar comandos como `tail`.  
Com recursos de **localização rápida de PDVs e PAY**, além de um **mapeamento de erros pré-catalogados**, o sistema transforma a análise de logs em uma tarefa ágil e visual.

---

## 🚀 Funcionalidades Principais

- 🔍 **Consulta web unificada** – interface intuitiva para pesquisar logs por data, hora, componente ou código de erro.
- 🤖 **Coleta automática de logs** – os logs são capturados em tempo real de todos os pontos da rede (PDVs, servidores PAY, backoffice) sem intervenção manual.
- 📍 **Localizador de PDVs e PAY** – identifique rapidamente qual PDV ou transação PAY gerou determinado log, mesmo em ambientes com dezenas de equipamentos.
- 🗺️ **Mapeamento de erros catalogados** – banco de conhecimento com erros conhecidos, suas causas e soluções sugeridas, exibidos junto ao log.
- 📊 **Visualização avançada** – gráficos de frequência de erros, linha do tempo, filtros por severidade e busca textual.
- ⚡ **Zero configuração de pastas** – diferente de sistemas que exigem `tail -f /var/log/...`, o LogFacil já entrega os logs organizados e pesquisáveis.
- 🔔 **Alertas proativos** – notificações quando um erro catalogado como crítico é detectado.

---

## 💾 Download do Executável (Windows)

**Para usar o LogFacil sem precisar instalar Python ou dependências, baixe o arquivo `.exe` da última versão:**

👉 [**Baixar LogFacil.exe - Último Release**](https://github.com/ejcastro1090/logfacil/releases/latest)

> Basta executar o arquivo baixado. O sistema abrirá automaticamente no seu navegador (endereço `http://localhost:8000`). Nenhuma configuração adicional é necessária.

---

## 🖥️ Interface Web

Acesse via navegador e comece a consultar imediatamente:

- **Dashboard principal** – últimos logs, resumo de erros por PDV.
- **Consulta avançada** – filtre por PDV, PAY, código de erro, período.
- **Visualização detalhada** – clique em qualquer log para ver o stack trace completo e sugestões do mapeamento de erros.
- **Exportação** – gere relatórios em CSV ou JSON.

---

## 🧩 Como Funciona

1. **Agentes coletores** (instalados nos PDVs e servidores) enviam logs para o centralizador.
2. O **backend** processa, indexa e armazena os logs (Elasticsearch ou SQLite).
3. O **frontend** consulta a API e exibe os resultados com realce de erros conhecidos.
4. O **mapeador de erros** cruza as mensagens com uma base interna de padrões (ex: `TIMEOUT_PAY`, `PDV_OFFLINE`, `IMPRESSORA_SEM_PAPEL`).

---

## 📦 Instalação a partir do código fonte (para desenvolvimento)

### Pré-requisitos
- Python 3.8+
- Node.js 16+ (para frontend, opcional se usar só backend)
- Acesso à rede dos PDVs (para coleta automática)

### Backend (API e coletor)

```bash
git clone https://github.com/ejcastro1090/logfacil.git
cd logfacil/backend
pip install -r requirements.txt
python app.py
