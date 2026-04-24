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
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

// App struct
type App struct {
	ctx          context.Context
	settings     *config.Settings
	mgr          *config.Manager
	lastIP       string                        // Rastreia o último IP para detectar mudanças
	serviceFiles map[string]string             // Cache dos arquivos de log por serviço
	watchers     map[string]*logFileWatcher    // Map de watchers ativos por caminho de arquivo
	mu           sync.RWMutex                  // Protege serviceFiles e watchers
	startCh      chan struct{}                  // Sinaliza que o frontend está pronto
}

// logFileWatcher gerencia o monitoramento de um único arquivo de log.
type logFileWatcher struct {
	serviceName string
	filePath    string
	file        *os.File
	lastSize    int64
	mu          sync.Mutex    // Protege file e lastSize - apenas um goroutine lê por vez
	ctx         context.Context
	cancel      context.CancelFunc
	app         *App
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
		settings:     settings,
		mgr:          mgr,
		serviceFiles: make(map[string]string),
		watchers:     make(map[string]*logFileWatcher),
		startCh:      make(chan struct{}),
	}
}

// FrontendReady é chamado pelo Vue quando todos os EventsOn estão registrados.
// Isso garante que o backend só emite eventos depois que a UI está pronta para receber.
func (a *App) FrontendReady() {
	select {
	case <-a.startCh:
		// canal já fechado, nada a fazer
	default:
		close(a.startCh)
		fmt.Println("[INFO] Frontend pronto - iniciando monitoramento de logs.")
	}
}

// startup é chamada quando o app inicia. Salva o context e inicia o loop de monitoramento.
func (a *App) startup(ctx context.Context) {
	a.ctx = ctx

	// Abre a janela maximizada ao iniciar
	runtime.WindowMaximise(ctx)

	// Aguarda o frontend sinalizar que está pronto (via FrontendReady())
	// com timeout de 8 segundos como fallback de segurança
	go func() {
		select {
		case <-a.startCh:
			// Frontend confirmou prontidão
		case <-time.After(8 * time.Second):
			fmt.Println("[WARN] FrontendReady não chamado em 8s, iniciando de qualquer forma")
		}
		a.monitorLogsLoop()
	}()

	if a.settings.AutoUpdate {
		go func() {
			time.Sleep(5 * time.Second)
			res := a.CheckForUpdates()
			if res.HasUpdate {
				runtime.EventsEmit(ctx, "update-available", res)
			}
		}()
	}
}

func (a *App) shutdown(ctx context.Context) {
	a.mu.Lock()
	defer a.mu.Unlock()
	for _, w := range a.watchers {
		w.cancel()
		w.closeFile()
	}
	fmt.Println("[INFO] App encerrado, todos os watchers parados.")
}

func (a *App) monitorLogsLoop() {
	tickerPDVs := time.NewTicker(5 * time.Second)
	tickerRefresh := time.NewTicker(1500 * time.Millisecond)
	tickerIP := time.NewTicker(60 * time.Second)
	
	defer tickerPDVs.Stop()
	defer tickerRefresh.Stop()
	defer tickerIP.Stop()

	// ACELERAÇÃO INICIAL: refresh a cada 500ms nos primeiros 10 segundos
	tickerRefresh.Reset(500 * time.Millisecond)
	go func() {
		time.Sleep(10 * time.Second)
		tickerRefresh.Reset(1500 * time.Millisecond)
		fmt.Println("[INFO] Warm-up completo, alternando para refresh normal (1.5s).")
	}()

	// Carga inicial
	a.refreshServiceFiles()

	for {
		select {
		case <-a.ctx.Done():
			return
		case <-tickerPDVs.C:
			res, err := a.GetPDVsFromLog()
			if err == nil {
				runtime.EventsEmit(a.ctx, "logs-updated", res)
			}
		case <-tickerRefresh.C:
			a.refreshServiceFiles()
		case <-tickerIP.C:
			currentIP := a.GetIP()
			if currentIP != a.lastIP {
				a.lastIP = currentIP
				runtime.EventsEmit(a.ctx, "ip-updated", currentIP)
			}
		}
	}
}

func (a *App) startWatching(serviceName, filePath string) {
	ctx, cancel := context.WithCancel(a.appContext())
	w := &logFileWatcher{
		serviceName: serviceName,
		filePath:    filePath,
		ctx:         ctx,
		cancel:      cancel,
		app:         a,
	}
	
	a.watchers[filePath] = w
	
	// A tailLoop já chama tailOnce() imediatamente ao iniciar - NÃO chamar aqui
	// para evitar race condition com dois goroutines lendo o mesmo arquivo.
	go w.tailLoop()
}

// Helper para obter o context do app (evita pânico se ctx ainda for nulo)
func (a *App) appContext() context.Context {
	if a.ctx != nil {
		return a.ctx
	}
	return context.Background()
}

func (a *App) refreshServiceFiles() {
	start := time.Now()
	rootPath := a.settings.LastFolder
	if rootPath == "" {
		rootPath = config.DefaultRoot
	}
	newMap := parser.ScanLatestServiceLogs(rootPath)

	a.mu.Lock()
	defer a.mu.Unlock()

	// 1. Detecta novos arquivos ou mudanças de caminho
	for svc, newPath := range newMap {
		oldPath, exists := a.serviceFiles[svc]
		if !exists || oldPath != newPath {
			// Se já tinha um watcher no caminho antigo, cancela ele
			if oldPath != "" {
				if w, ok := a.watchers[oldPath]; ok {
					w.cancel()
					w.closeFile()
					delete(a.watchers, oldPath)
				}
			}
			// Inicia novo watcher
			a.startWatching(svc, newPath)
			a.serviceFiles[svc] = newPath
		}
	}

	// 2. Remove watchers de arquivos que não existem mais na descoberta
	for path, w := range a.watchers {
		found := false
		for _, p := range newMap {
			if p == path {
				found = true
				break
			}
		}
		if !found {
			w.cancel()
			w.closeFile()
			delete(a.watchers, path)
			// Limpa de serviceFiles também
			for s, p := range a.serviceFiles {
				if p == path {
					delete(a.serviceFiles, s)
					break
				}
			}
		}
	}
	fmt.Printf("[PERF] Discovery de arquivos levou %v\n", time.Since(start))
}

// ─────────────────────────────────────────────────────────────────────────────
// LÓGICA DE WATCHER (BASEADA NO PYTHON)
// ─────────────────────────────────────────────────────────────────────────────

func (w *logFileWatcher) tailLoop() {
	// Primeira leitura imediata ao iniciar o loop (ignora o primeiro tick do ticker)
	w.tailOnce()

	// Intervalo de leitura idêntico ao Python (250ms)
	ticker := time.NewTicker(250 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-w.ctx.Done():
			w.closeFile()
			return
		case <-ticker.C:
			w.tailOnce()
		}
	}
}

func (w *logFileWatcher) tailOnce() {
	// Garante que apenas um goroutine lê este arquivo por vez
	w.mu.Lock()
	defer w.mu.Unlock()

	// 1. Abrir ou reabrir se necessário
	if w.file == nil {
		f, err := os.Open(w.filePath)
		if err != nil {
			return
		}
		info, err := f.Stat()
		if err != nil {
			f.Close()
			return
		}

		// Determina o ponto de partida da leitura
		var start int64
		maxStart := int64(config.MaxStartBytes) // 128KB padrão

		// Se o arquivo é antigo (não modificado há mais de 1h), 
		// aumentamos o buffer inicial para 1MB para garantir que o usuário veja contexto.
		if time.Since(info.ModTime()) > time.Hour {
			maxStart = 1024 * 1024 // 1MB
			fmt.Printf("[INFO] Log antigo detectado (%s). Aumentando buffer inicial para 1MB.\n", w.serviceName)
		}

		start = info.Size() - maxStart
		if start < 0 {
			start = 0
		}
		
		_, _ = f.Seek(start, 0)
		w.file = f
		w.lastSize = start 
	}

	// 2. Verificar rotação ou mudanças (usando a mesma lógica do Python)
	info, err := w.file.Stat()
	if err != nil {
		w.closeFile()
		return
	}

	currentSize := info.Size()

	// Se o arquivo encolheu -> ROTACIONOU
	if currentSize < w.lastSize {
		fmt.Printf("[INFO] Rotação detectada para %s: %s\n", w.serviceName, w.filePath)
		w.closeFile()
		return
	}

	// 3. Ler novos bytes em loop para não lagar em arquivos grandes (Draine)
	for {
		toRead := currentSize - w.lastSize
		if toRead <= 0 {
			break
		}

		if toRead > 1024*1024 { // Cap de 1MB por iteração
			toRead = 1024 * 1024
		}

		buf := make([]byte, toRead)
		n, err := w.file.Read(buf)
		if err != nil && err != io.EOF {
			w.closeFile()
			return
		}

		if n > 0 {
			w.lastSize += int64(n)
			content := parser.DecodeToUTF8(buf[:n])

			// Emite para a UI
			runtime.EventsEmit(w.app.ctx, "service-log-append", parser.ServiceLogUpdate{
				Service: w.serviceName,
				Content: content,
			})
		}

		if n < int(toRead) {
			break
		}

		// Atualiza currentSize para a próxima iteração do loop
		info, err = w.file.Stat()
		if err != nil {
			break
		}
		currentSize = info.Size()
	}
}

func (w *logFileWatcher) closeFile() {
	if w.file != nil {
		w.file.Close()
		w.file = nil
	}
	w.lastSize = 0
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
	
	// Reseta se a pasta raiz mudou
	if oldFolder != s.LastFolder {
		a.mu.Lock()
		for _, w := range a.watchers {
			w.cancel()
			w.closeFile()
		}
		a.watchers = make(map[string]*logFileWatcher)
		a.serviceFiles = make(map[string]string)
		a.mu.Unlock()
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
		// Reseta para a nova pasta
		a.mu.Lock()
		for _, w := range a.watchers {
			w.cancel()
			w.closeFile()
		}
		a.watchers = make(map[string]*logFileWatcher)
		a.serviceFiles = make(map[string]string)
		a.mu.Unlock()
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

func (a *App) GetAppVersion() string {
	return config.Version
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
