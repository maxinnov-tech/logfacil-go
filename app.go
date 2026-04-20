package main

import (
	"archive/zip"
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"logf/backend/config"
	"logf/backend/parser"
	"logf/backend/systools"
	"logf/backend/updater"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct
type App struct {
	ctx         context.Context
	settings    *config.Settings
	mgr         *config.Manager
	lastOffsets map[string]int64
	lastIP      string // Rastreia o último IP para detectar mudanças
}

type ComponentStatus struct {
	Name     string         `json:"name"`
	IsOk     bool           `json:"is_ok"`
	Status   string         `json:"status"`
	Services []ServiceState `json:"services"`
}

type ServiceState struct {
	Name    string `json:"name"`
	Running bool   `json:"running"`
	Message string `json:"message"`
}

type PDVResponse struct {
	PDVs    []parser.PDVInfo `json:"pdvs"`
	Message string           `json:"message"`
}

// NewApp creates a new App application struct
func NewApp() *App {
	mgr := config.NewManager()
	settings, _ := mgr.Load()
	return &App{
		settings:    settings,
		mgr:         mgr,
		lastOffsets: make(map[string]int64),
	}
}

// startup é chamada quando o app inicia. Salva o context e inicia o loop de monitoramento.
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
	go a.monitorLogsLoop()

	if a.settings.AutoUpdate {
		go func() {
			time.Sleep(3 * time.Second) // aguarda um pouco para não travar o início
			res := a.CheckForUpdates()
			if res.HasUpdate {
				runtime.EventsEmit(ctx, "update-available", res)
			}
		}()
	}
}

func (a *App) monitorLogsLoop() {
	// Intervalo do ticker de PDVs: 5 segundos (SCAN_INTERVAL_SEC do Python)
	tickerLogs := time.NewTicker(5 * time.Second)
	// Intervalo do tail: 200ms (TAIL_POLL_INTERVAL_SEC ≈ 0.25s → arredondado para 200ms)
	tickerTail := time.NewTicker(200 * time.Millisecond)
	// Intervalo de verificação de IP: 60 segundos conforme solicitado pelo usuário
	tickerIP := time.NewTicker(60 * time.Second)
	
	defer tickerLogs.Stop()
	defer tickerTail.Stop()
	defer tickerIP.Stop()

	for {
		select {
		case <-a.ctx.Done():
			return
		case <-tickerLogs.C:
			res, err := a.GetPDVsFromLog()
			if err == nil {
				runtime.EventsEmit(a.ctx, "logs-updated", res)
			}
		case <-tickerTail.C:
			a.tailAllServiceLogs()
		case <-tickerIP.C:
			currentIP := a.GetIP()
			if currentIP != a.lastIP {
				a.lastIP = currentIP
				runtime.EventsEmit(a.ctx, "ip-updated", currentIP)
			}
		}
	}
}

func (a *App) tailAllServiceLogs() {
	rootPath := a.settings.LastFolder
	if rootPath == "" {
		rootPath = config.DefaultRoot
	}

	serviceFiles := parser.ScanLatestServiceLogs(rootPath)
	for svc, path := range serviceFiles {
		a.tailFile(svc, path)
	}
}

func (a *App) tailFile(serviceName, path string) {
	file, err := os.Open(path)
	if err != nil {
		return
	}
	defer file.Close()

	info, err := file.Stat()
	if err != nil {
		return
	}

	lastOffset, exists := a.lastOffsets[path]

	// Se for um arquivo novo ou encolheu (log rotacionado)
	// BareTail effect: posiciona MAX_START_BYTES antes do fim para mostrar histórico recente
	if !exists || info.Size() < lastOffset {
		start := info.Size() - int64(config.MaxStartBytes)
		if start < 0 {
			start = 0
		}
		lastOffset = start
		a.lastOffsets[path] = start
	}

	if info.Size() > lastOffset {
		_, err := file.Seek(lastOffset, 0)
		if err != nil {
			return
		}

		content := make([]byte, info.Size()-lastOffset)
		_, err = file.Read(content)
		if err != nil {
			return
		}

		a.lastOffsets[path] = info.Size()

		// Decodifica encoding automaticamente: cp1252 → latin-1 → utf-8
		// Replica ENCODINGS = ("cp1252", "latin-1", "utf-8") do Python (core/config.py)
		runtime.EventsEmit(a.ctx, "service-log-append", parser.ServiceLogUpdate{
			Service: serviceName,
			Content: parser.DecodeToUTF8(content),
		})
	}
}

// =============================================================================
// CONFIGURAÇÕES
// =============================================================================

func (a *App) GetSettings() *config.Settings {
	return a.settings
}

func (a *App) GetLogMarkers() []config.LogMarker {
	return config.DefaultMarkers
}

func (a *App) SaveSettings(s config.Settings) error {
	oldFolder := a.settings.LastFolder
	a.settings = &s
	// Reseta offsets se a pasta raiz mudou (relê os logs da nova pasta)
	if oldFolder != s.LastFolder {
		a.lastOffsets = make(map[string]int64)
	}
	return a.mgr.Save(a.settings)
}

// ChooseFolder abre um diálogo nativo para o usuário escolher a pasta de logs.
// Equivalente ao _choose_root() do Python (gui/app.py).
func (a *App) ChooseFolder() (string, error) {
	folder, err := runtime.OpenDirectoryDialog(a.ctx, runtime.OpenDialogOptions{
		Title:            "Selecionar Pasta de Logs",
		DefaultDirectory: a.settings.LastFolder,
		ShowHiddenFiles:  false,
	})
	if err != nil {
		return "", err
	}
	if folder != "" {
		a.settings.LastFolder = folder
		_ = a.mgr.Save(a.settings)
		// Reseta os offsets para que o tail releia os logs da nova pasta
		a.lastOffsets = make(map[string]int64)
	}
	return folder, nil
}

// =============================================================================
// SISTEMA
// =============================================================================

func (a *App) IsAdmin() bool {
	return systools.IsAdmin()
}

func (a *App) GetIP() string {
	return systools.GetMainIP()
}

func (a *App) RestartAsAdmin() error {
	err := systools.RunAsAdmin()
	if err == nil {
		os.Exit(0) // Fecha a instância atual após disparar a nova
	}
	return err
}

// =============================================================================
// ATUALIZAÇÃO
// =============================================================================

func (a *App) CheckForUpdates() updater.UpdateResponse {
	return updater.CheckForUpdates(config.GithubRepo, config.Version)
}

func (a *App) DownloadAndInstallUpdate(downloadUrl string) (bool, string) {
	appPath, err := os.Executable()
	if err != nil {
		return false, "Erro ao obter caminho do executável: " + err.Error()
	}

	downloadedFilePath, err := updater.DownloadUpdate(a.ctx, downloadUrl)
	if err != nil {
		return false, "Erro no download: " + err.Error()
	}

	err = updater.InstallUpdate(appPath, downloadedFilePath)
	if err != nil {
		return false, "Erro ao preparar instalação: " + err.Error()
	}

	// Aguarda curto período para o BAT iniciar na retaguarda e fecha o próprio App
	time.Sleep(500 * time.Millisecond)
	os.Exit(0)
	
	return true, "A instalação foi iniciada."
}

// =============================================================================
// LOGS E PDVs
// =============================================================================

// GetPDVsFromLog usa a lógica completa de cruzamento igual ao Python.
// Equivalente ao identificar_todos_pdvs_por_log() do Python (core/pdv_parser.py).
func (a *App) GetPDVsFromLog() (*PDVResponse, error) {
	rootPath := a.settings.LastFolder
	if rootPath == "" {
		rootPath = config.DefaultRoot
	}

	fmt.Printf("[DEBUG] Iniciando varredura em: %s\n", rootPath)

	pdvs, msg := parser.IdentificarTodosPDVsPorLog(rootPath)

	fmt.Printf("[DEBUG] Resumo: %s\n", msg)

	return &PDVResponse{
		PDVs:    pdvs,
		Message: msg,
	}, nil
}

// GetPDVsRaw retorna os PDVs extraídos diretamente do log (sem cruzamento com API).
// Usado internamente para monitoramento de atividade.
func (a *App) GetPDVsRaw() (*PDVResponse, error) {
	rootPath := a.settings.LastFolder
	if rootPath == "" {
		rootPath = config.DefaultRoot
	}

	logFiles := parser.ListarTodosOsLogsRecentes(rootPath)
	if len(logFiles) == 0 {
		return &PDVResponse{
			PDVs:    []parser.PDVInfo{},
			Message: "Nenhum arquivo de log encontrado em " + rootPath,
		}, nil
	}

	allAtividades := make(map[string]parser.LogPDVActivity)
	for _, path := range logFiles {
		atividades, err := parser.ExtrairAtividadesDoLog(path)
		if err == nil {
			for _, at := range atividades {
				allAtividades[at.PDVIDQ] = at
			}
		}
	}

	var result []parser.PDVInfo
	for _, at := range allAtividades {
		nome := "PDV " + at.PDVReferencia
		ip := at.IP
		if ip == "" || ip == "localhost" {
			ip = "127.0.0.1"
		}
		result = append(result, parser.PDVInfo{
			Codigo:    at.PDVReferencia,
			IDInterno: at.PDVIDQ,
			Nome:      nome,
			IP:        ip,
			Operando:  true,
		})
	}

	msg := fmt.Sprintf("Varredura em %d arquivos. %d PDVs ativos.", len(logFiles), len(result))
	return &PDVResponse{PDVs: result, Message: msg}, nil
}

// ExportPDVsCSV exporta o histórico de PDVs fornecido como CSV.
// Equivalente ao _exportar_historico() do Python (gui/tabs/pdv_tab.py).
func (a *App) ExportPDVsCSV(pdvs []parser.PDVInfo) (bool, string) {
	savePath, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "Exportar Histórico de PDVs",
		DefaultFilename: fmt.Sprintf("PDVs_Exportados_%s.csv", time.Now().Format("20060102_1504")),
		Filters: []runtime.FileFilter{
			{DisplayName: "Arquivo CSV (*.csv)", Pattern: "*.csv"},
		},
	})

	if err != nil || savePath == "" {
		return false, "Operação cancelada."
	}

	f, err := os.Create(savePath)
	if err != nil {
		return false, "Erro ao criar arquivo: " + err.Error()
	}
	defer f.Close()

	// BOM para UTF-8 (compatível com Excel, igual ao Python utf-8-sig)
	f.Write([]byte{0xEF, 0xBB, 0xBF})

	w := csv.NewWriter(f)
	w.Comma = ';'
	_ = w.Write([]string{"Código", "Nome", "IP", "ID Interno", "Tipo", "Status"})

	for _, p := range pdvs {
		tipo := p.Tipo
		if tipo == "" {
			tipo = "M"
		}
		status := "Ativo"
		if !p.Operando {
			status = "Inativo"
		}
		_ = w.Write([]string{p.Codigo, p.Nome, p.IP, p.IDInterno, tipo, status})
	}
	w.Flush()

	if err := w.Error(); err != nil {
		return false, "Erro ao escrever CSV: " + err.Error()
	}

	return true, fmt.Sprintf("CSV exportado com %d PDVs em: %s", len(pdvs), savePath)
}

// =============================================================================
// SERVIÇOS
// =============================================================================

func (a *App) GetServiceStatuses() []ComponentStatus {
	var result []ComponentStatus
	for _, comp := range config.ServiceComponents {
		cStatus := ComponentStatus{
			Name: comp.Name,
			IsOk: true,
		}

		if len(comp.Services) == 0 {
			cStatus.Status = "Monitorando Processos"
		}

		for _, svc := range comp.Services {
			exists, running, msg := systools.CheckServiceStatus(svc)
			cStatus.Services = append(cStatus.Services, ServiceState{
				Name:    svc,
				Running: running,
				Message: msg,
			})
			if !exists || !running {
				cStatus.IsOk = false
			}
		}

		if cStatus.IsOk && len(comp.Services) > 0 {
			cStatus.Status = "Em execução"
		} else if !cStatus.IsOk {
			cStatus.Status = "Atenção / Parado"
		}

		result = append(result, cStatus)
	}
	return result
}

func (a *App) RestartComponent(name string) (bool, string) {
	if !systools.IsAdmin() {
		return false, "Privilégios de administrador necessários"
	}

	var target *config.ServiceComponent
	for i, c := range config.ServiceComponents {
		if c.Name == name {
			cp := config.ServiceComponents[i]
			target = &cp
			break
		}
	}

	if target == nil {
		return false, "Serviço não encontrado"
	}

	// 1. Para os serviços (ordem reversa, igual ao Python)
	for i := len(target.Services) - 1; i >= 0; i-- {
		systools.StopWindowsService(target.Services[i])
	}

	// 2. Mata processos
	for _, task := range target.Tasks {
		systools.KillTask(task)
	}

	time.Sleep(1 * time.Second)

	// 3. Inicia serviços
	allOk := true
	var lastMsg string
	for _, svc := range target.Services {
		ok, msg := systools.StartWindowsService(svc)
		if !ok {
			allOk = false
			lastMsg = msg
		}
	}

	if allOk {
		return true, fmt.Sprintf("Serviço '%s' reiniciado com sucesso!", name)
	}
	return false, "Erro ao iniciar serviços: " + lastMsg
}

// =============================================================================
// EXPORTAÇÃO
// =============================================================================

func (a *App) GetExportFolders() []string {
	root := a.settings.LastFolder
	if root == "" {
		root = config.DefaultRoot
	}

	// Resolve a pasta LOG corretamente (idêntico ao Python)
	scanRoot := parser.ResolveLogRoot(root)

	entries, err := os.ReadDir(scanRoot)
	if err != nil {
		return []string{}
	}

	var folders []string
	for _, e := range entries {
		if e.IsDir() {
			folders = append(folders, e.Name())
		}
	}
	sort.Strings(folders)
	return folders
}

// ExportLogs exporta logs selecionados para um ZIP com filtro de data.
// Corrigido para paridade com o Python (export_tab.py):
// - Período "0" = Hoje (limitStart + limitEnd corretos)
// - Fallback silencioso: se filtro resultar em 0 arquivos mas existem arquivos disponíveis, exporta tudo
func (a *App) ExportLogs(folders []string, period string, customStart, customEnd string) (bool, string) {
	savePath, err := runtime.SaveFileDialog(a.ctx, runtime.SaveDialogOptions{
		Title:           "Salvar Logs Exportados",
		DefaultFilename: fmt.Sprintf("Logs_Exportados_%s.zip", time.Now().Format("20060102_1504")),
		Filters: []runtime.FileFilter{
			{DisplayName: "Arquivo ZIP (*.zip)", Pattern: "*.zip"},
		},
	})

	if err != nil || savePath == "" {
		return false, "Operação cancelada ou falha ao selecionar local."
	}

	// Lógica de filtro de datas — idêntica ao Python (export_tab.py)
	var limitStart, limitEnd time.Time
	now := time.Now()

	switch period {
	case "0": // Hoje
		limitStart = time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, now.Location())
		limitEnd = time.Date(now.Year(), now.Month(), now.Day(), 23, 59, 59, 0, now.Location())
	case "7", "15", "30":
		days, _ := strconv.Atoi(period)
		limitStart = now.AddDate(0, 0, -days)
		limitStart = time.Date(limitStart.Year(), limitStart.Month(), limitStart.Day(), 0, 0, 0, 0, now.Location())
		limitEnd = time.Date(now.Year(), now.Month(), now.Day(), 23, 59, 59, 0, now.Location())
	case "custom":
		layout := "02/01/2006"
		if s, err := time.Parse(layout, customStart); err == nil {
			limitStart = time.Date(s.Year(), s.Month(), s.Day(), 0, 0, 0, 0, now.Location())
		}
		if e, err := time.Parse(layout, customEnd); err == nil {
			limitEnd = time.Date(e.Year(), e.Month(), e.Day(), 23, 59, 59, 0, now.Location())
		}
	case "all":
		// Sem filtro
	}

	// Criar ZIP
	newZipFile, err := os.Create(savePath)
	if err != nil {
		return false, "Erro ao criar arquivo: " + err.Error()
	}
	defer newZipFile.Close()

	zipWriter := zip.NewWriter(newZipFile)
	defer zipWriter.Close()

	rootPath := a.settings.LastFolder
	if rootPath == "" {
		rootPath = config.DefaultRoot
	}
	scanRoot := parser.ResolveLogRoot(rootPath)

	// Coleta arquivos com filtro e também todos os disponíveis (para fallback)
	var filesToZip []string
	var allAvailable []string

	for _, fName := range folders {
		folderPath := filepath.Join(scanRoot, fName)
		filepath.Walk(folderPath, func(path string, info os.FileInfo, err error) error {
			if err != nil || info.IsDir() {
				return nil
			}

			mtime := info.ModTime()
			allAvailable = append(allAvailable, path)

			if !limitStart.IsZero() && mtime.Before(limitStart) {
				return nil
			}
			if !limitEnd.IsZero() && mtime.After(limitEnd) {
				return nil
			}

			filesToZip = append(filesToZip, path)
			return nil
		})
	}

	// Fallback silencioso — idêntico ao Python (export_tab.py _do_export):
	// Se filtro de data resultou em vazio mas há arquivos disponíveis, exporta tudo
	if len(filesToZip) == 0 && !limitStart.IsZero() && len(allAvailable) > 0 {
		filesToZip = allAvailable
	}

	if len(filesToZip) == 0 {
		return false, "Nenhum arquivo encontrado nas pastas selecionadas."
	}

	count := 0
	for _, path := range filesToZip {
		relPath, _ := filepath.Rel(scanRoot, path)
		// Normaliza separadores para o ZIP (usa /)
		relPath = strings.ReplaceAll(relPath, "\\", "/")
		w, err := zipWriter.Create(relPath)
		if err != nil {
			continue
		}
		fileToZip, err := os.Open(path)
		if err != nil {
			continue
		}
		io.Copy(w, fileToZip)
		fileToZip.Close()
		count++
	}

	return true, fmt.Sprintf("Exportação concluída! %d arquivos compactados.", count)
}
