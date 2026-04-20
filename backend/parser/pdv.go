package parser

import (
	"bufio"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"logf/backend/config"
	"logf/backend/systools"
)

// PDVInfo representa os dados básicos de um PDV.
// Idêntico ao modelo PDVInfo do Python (models/pdv.py).
type PDVInfo struct {
	Codigo        string `xml:"cd_pdv" json:"codigo"`
	IDInterno     string `xml:"idq_pdv" json:"id_interno"`
	Nome          string `xml:"nome_pdv" json:"nome"`
	Tipo          string `xml:"tipo" json:"tipo"`
	Operando      bool   `json:"operando"`
	Serial        string `xml:"posSerial" json:"serial"`
	CodigoEstoque string `xml:"codigoEstoque" json:"codigo_estoque"`
	IP            string `json:"ip"`
}

// LogPDVActivity representa uma atividade extraída dos logs.
// Idêntico ao LogPDVActivity do Python (models/pdv.py).
type LogPDVActivity struct {
	PDVIDQ          string `json:"pdv_idq"`
	PDVReferencia   string `json:"pdv_referencia"`
	Funcionario     string `json:"funcionario"`
	IP              string `json:"ip"`
	VersaoApp       string `json:"versao_app"`
	UltimaAtividade string `json:"ultima_atividade"`
}

// ServiceLogUpdate representa um bloco de texto lido de um log específico.
type ServiceLogUpdate struct {
	Service string `json:"service"`
	Content string `json:"content"`
}

var (
	reIDQ    = regexp.MustCompile(`pdv_idq:\[(\d+)\]`)
	reRef    = regexp.MustCompile(`pdv_referencia:\[(\d+)\]`)
	reFunc   = regexp.MustCompile(`funcionario:\[(\d+)\]`)
	reIP     = regexp.MustCompile(`host:\[([a-zA-Z0-9.]+):\d+\]`)
	reVersao = regexp.MustCompile(`app_version:\[([0-9.]+)\]`)
	reHora   = regexp.MustCompile(`(\d{2}:\d{2}:\d{2})`)

	// Regexes para o formato JSON do PAF
	rePafID      = regexp.MustCompile(`sidCdSistemaDispositivo":"(\d+)"`)
	rePafIP      = regexp.MustCompile(`sidDsIpDispositivo":"([a-zA-Z0-9.]+)"`)
	rePafVersion = regexp.MustCompile(`sidDsVersao":"([0-9.]+)"`)
	rePafRef     = regexp.MustCompile(`sidDsDispositivoNome":"([^"]+)"`)
)

// ExtrairAtividadesDoLog lê as últimas linhas do log e extrai atividades dos PDVs.
// Idêntico ao extrair_todos_pdvs_do_log() do Python (core/pdv_parser.py).
func ExtrairAtividadesDoLog(caminhoLog string) ([]LogPDVActivity, error) {
	file, err := os.Open(caminhoLog)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return nil, err
	}

	// Igual ao Python: lê as últimas 128KB (MAX_START_BYTES)
	start := int64(0)
	if info.Size() > int64(config.MaxStartBytes) {
		start = info.Size() - int64(config.MaxStartBytes)
	}

	_, err = file.Seek(start, 0)
	if err != nil {
		return nil, err
	}

	// Lê todo o bloco de uma vez para decodificar encoding antes do scanner
	// Replica ENCODINGS = ("cp1252", "latin-1", "utf-8") do Python (core/config.py)
	rawContent, err := io.ReadAll(file)
	if err != nil {
		return nil, err
	}
	decoded := DecodeToUTF8(rawContent)

	scanner := bufio.NewScanner(strings.NewReader(decoded))
	buf := make([]byte, 1024*1024)
	scanner.Buffer(buf, 1024*1024)

	pdvsEncontrados := make(map[string]*LogPDVActivity)

	for scanner.Scan() {
		linha := scanner.Text()

		// 1. Tenta formato PayServer (pdv_idq:[...])
		matchIDQ := reIDQ.FindStringSubmatch(linha)
		if len(matchIDQ) > 1 {
			idq := matchIDQ[1]
			atividade, ok := pdvsEncontrados[idq]
			if !ok {
				atividade = &LogPDVActivity{PDVIDQ: idq}
				pdvsEncontrados[idq] = atividade
			}

			if m := reRef.FindStringSubmatch(linha); len(m) > 1 && atividade.PDVReferencia == "" {
				atividade.PDVReferencia = m[1]
			}
			if m := reFunc.FindStringSubmatch(linha); len(m) > 1 && atividade.Funcionario == "" {
				atividade.Funcionario = m[1]
			}
			if m := reIP.FindStringSubmatch(linha); len(m) > 1 && atividade.IP == "" {
				atividade.IP = m[1]
			}
			if m := reVersao.FindStringSubmatch(linha); len(m) > 1 && atividade.VersaoApp == "" {
				atividade.VersaoApp = m[1]
			}
			if m := reHora.FindStringSubmatch(linha); len(m) > 1 {
				atividade.UltimaAtividade = m[1]
			}
			continue
		}

		// 2. Tenta formato PAF (sidCdSistemaDispositivo:"...")
		matchPafID := rePafID.FindStringSubmatch(linha)
		if len(matchPafID) > 1 {
			idq := matchPafID[1]
			atividade, ok := pdvsEncontrados[idq]
			if !ok {
				atividade = &LogPDVActivity{PDVIDQ: idq}
				pdvsEncontrados[idq] = atividade
			}

			if m := rePafRef.FindStringSubmatch(linha); len(m) > 1 && atividade.PDVReferencia == "" {
				atividade.PDVReferencia = m[1]
			}
			if m := rePafIP.FindStringSubmatch(linha); len(m) > 1 && atividade.IP == "" {
				atividade.IP = m[1]
			}
			if m := rePafVersion.FindStringSubmatch(linha); len(m) > 1 && atividade.VersaoApp == "" {
				atividade.VersaoApp = m[1]
			}
			if m := reHora.FindStringSubmatch(linha); len(m) > 1 {
				atividade.UltimaAtividade = m[1]
			}
		}
	}

	atividades := make([]LogPDVActivity, 0, len(pdvsEncontrados))
	for _, a := range pdvsEncontrados {
		atividades = append(atividades, *a)
	}
	return atividades, scanner.Err()
}

// hasLogExtension verifica se um arquivo tem extensão de log conhecida.
// Reproduz as LOG_EXTENSIONS do Python (core/config.py).
func hasLogExtension(name string) bool {
	ext := strings.ToLower(filepath.Ext(name))
	for _, e := range config.LogExtensions {
		if ext == e {
			return true
		}
	}
	return false
}

// ResolveLogRoot resolve a pasta raiz de logs.
// Idêntico ao scan_log_files() do Python (core/utils.py):
// se o root não se chama "LOG", procura a subpasta "LOG" dentro dele.
func ResolveLogRoot(root string) string {
	base := strings.ToUpper(filepath.Base(filepath.Clean(root)))
	if base == "LOG" {
		return root
	}
	candidate := filepath.Join(root, "LOG")
	if info, err := os.Stat(candidate); err == nil && info.IsDir() {
		return candidate
	}
	return root
}

// ListarTodosOsLogsRecentes percorre recursivamente a pasta raiz e retorna todos os arquivos de log.
// Suporta todas as extensões de LOG_EXTENSIONS (idêntico ao Python).
func ListarTodosOsLogsRecentes(root string) []string {
	scanRoot := ResolveLogRoot(root)
	var logs []string
	filepath.Walk(scanRoot, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			fmt.Printf("[ERRO] Falha ao acessar %s: %v\n", path, err)
			return nil
		}
		if !info.IsDir() && hasLogExtension(info.Name()) {
			logs = append(logs, path)
		}
		return nil
	})
	return logs
}

// ConsultarPDVsViaAPI busca a lista de todos os PDVs via API XML local.
// Idêntico ao consultar_todos_pdvs_via_api() do Python (core/pdv_parser.py).
func ConsultarPDVsViaAPI(baseURL string) ([]PDVInfo, error) {
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequest("GET", baseURL+"/pdv", nil)
	if err != nil {
		return nil, err
	}

	// Headers idênticos ao Python
	req.Header.Set("pdv_idq", "38545")
	req.Header.Set("pdv_referencia", "002")
	req.Header.Set("funcionario", "00001")
	req.Header.Set("Content-Type", "application/xml")
	req.Header.Set("Accept", "application/xml")

	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("API retornou status %d", resp.StatusCode)
	}

	var result struct {
		Items []PDVInfo `xml:"item"`
	}
	if err := xml.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}

	// Filtra PDVs sem código e sem id_interno
	pdvs := make([]PDVInfo, 0)
	for _, p := range result.Items {
		if p.Codigo != "" || p.IDInterno != "" {
			pdvs = append(pdvs, p)
		}
	}

	return pdvs, nil
}

// IdentificarTodosPDVsPorLog realiza o cruzamento completo entre os logs e a API.
// Idêntico ao identificar_todos_pdvs_por_log() do Python (core/pdv_parser.py).
func IdentificarTodosPDVsPorLog(pastaLog string) ([]PDVInfo, string) {
	mainIP := systools.GetMainIP()

	// 1. Busca todos os PDVs na API
	todosAPI, _ := ConsultarPDVsViaAPI(config.DefaultAPIBase)
	pdvsPorID := make(map[string]PDVInfo)
	for _, p := range todosAPI {
		pdvsPorID[p.IDInterno] = p
	}

	// 2. Encontra o log mais recente do webPostoPayServer
	logPath, _ := EncontrarUltimoLog(pastaLog)

	// 3. Extrai atividades do log
	var atividadesLog []LogPDVActivity
	if logPath != "" {
		atividadesLog, _ = ExtrairAtividadesDoLog(logPath)
	}

	// 4. Cruza atividades com a API
	pdvsEncontrados := make([]PDVInfo, 0)
	mensagens := make([]string, 0)

	for _, atividade := range atividadesLog {
		if atividade.PDVIDQ == "" {
			continue
		}

		ip := atividade.IP
		if ip == "" || ip == "localhost" {
			ip = mainIP
		}

		if pdv, ok := pdvsPorID[atividade.PDVIDQ]; ok {
			pdv.IP = ip
			pdvsEncontrados = append(pdvsEncontrados, pdv)
			mensagens = append(mensagens, fmt.Sprintf("PDV %s - %s", pdv.Codigo, pdv.Nome))
		} else {
			// PDV não cadastrado na API — cria registro temporário
			codigo := atividade.PDVReferencia
			if codigo == "" {
				codigo = fmt.Sprintf("PDV_%s", atividade.PDVIDQ)
			}
			nome := fmt.Sprintf("PDV %s", atividade.PDVReferencia)
			if atividade.PDVReferencia == "" {
				nome = fmt.Sprintf("PDV %s", atividade.PDVIDQ)
			}
			pdvsEncontrados = append(pdvsEncontrados, PDVInfo{
				Codigo:    codigo,
				IDInterno: atividade.PDVIDQ,
				Nome:      nome,
				Tipo:      "M",
				Operando:  true,
				Serial:    "N/A",
				IP:        ip,
			})
			mensagens = append(mensagens, fmt.Sprintf("PDV não cadastrado - IDQ: %s", atividade.PDVIDQ))
		}
	}

	// 5. Fallback idêntico ao Python:
	// Se nenhum PDV foi identificado no log mas a API retornou PDVs do tipo 'M' e operando, usa eles
	if len(pdvsEncontrados) == 0 && len(todosAPI) > 0 {
		for _, p := range todosAPI {
			if p.Tipo == "M" && p.Operando {
				p.IP = mainIP
				pdvsEncontrados = append(pdvsEncontrados, p)
				mensagens = append(mensagens, fmt.Sprintf("PDV PAY: %s - %s", p.Codigo, p.Nome))
			}
		}
	}

	if len(pdvsEncontrados) > 0 {
		msg := fmt.Sprintf("Total: %d\n%s", len(pdvsEncontrados), strings.Join(mensagens, "\n"))
		return pdvsEncontrados, msg
	}

	return []PDVInfo{}, "Nenhum PDV identificado"
}

// EncontrarUltimoLog procura o arquivo de log mais recente na pasta webPostoPayServer.
// Idêntico ao encontrar_log_webPostoPayServer() do Python (core/pdv_parser.py).
func EncontrarUltimoLog(pastaLog string) (string, error) {
	alvo := filepath.Join(ResolveLogRoot(pastaLog), "webPostoPayServer")
	var latestFile string
	var latestTime time.Time

	err := filepath.Walk(alvo, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if hasLogExtension(info.Name()) {
			if info.ModTime().After(latestTime) {
				latestTime = info.ModTime()
				latestFile = path
			}
		}
		return nil
	})

	return latestFile, err
}

// ScanLatestServiceLogs percorre as subpastas em root e retorna mapa [NomeServico]CaminhoArquivo mais recente.
// Usa ResolveLogRoot para localizar corretamente a pasta LOG (idêntico ao Python).
func ScanLatestServiceLogs(root string) map[string]string {
	result := make(map[string]string)
	scanRoot := ResolveLogRoot(root)

	entries, err := os.ReadDir(scanRoot)
	if err != nil {
		fmt.Printf("[ERRO] Falha ao ler pasta raiz: %v\n", err)
		return result
	}

	for _, e := range entries {
		if e.IsDir() {
			serviceName := e.Name()
			servicePath := filepath.Join(scanRoot, serviceName)

			latest, err := findLatestLogFile(servicePath)
			if err == nil && latest != "" {
				result[serviceName] = latest
			}
		}
	}

	return result
}

// findLatestLogFile encontra o arquivo de log mais recente em uma pasta (recursivo).
// Suporta todas as extensões de LOG_EXTENSIONS (idêntico ao Python).
func findLatestLogFile(dir string) (string, error) {
	var latestFile string
	var latestTime time.Time

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		if hasLogExtension(info.Name()) {
			if info.ModTime().After(latestTime) {
				latestTime = info.ModTime()
				latestFile = path
			}
		}
		return nil
	})

	return latestFile, err
}
