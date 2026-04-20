package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

const (
	Version        = "2.1.3-GO"
	GithubRepo     = "maxinnov-tech/logfacil-go"
	DefaultRoot    = "C:\\Quality\\LOG"
	DefaultAPIBase = "http://localhost:8080"

	// Intervalos idênticos ao Python
	ScanIntervalSec     = 5
	TailPollMs          = 200
	MaxStartBytes       = 128 * 1024
	DefaultMaxViewLines = 1000
	DefaultFontSize     = 13
	DefaultScanInterval = 2.0
)

// LogExtensions reproduz exatamente as extensões do Python (LOG_EXTENSIONS)
var LogExtensions = []string{".log", ".txt", ".out", ".err", ".trace", ".debug"}

// ServiceComponent define a estrutura de um componente monitorado.
type ServiceComponent struct {
	Name     string   `json:"name"`
	Services []string `json:"services"`
	Tasks    []string `json:"tasks"`
}

var ServiceComponents = []ServiceComponent{
	{Name: "Integra", Services: []string{"srvIntegraWeb"}, Tasks: []string{"IntegraWebService.exe"}},
	{Name: "PulserWeb", Services: []string{}, Tasks: []string{"PulserWeb.exe"}},
	{Name: "webPostoFiscalServer", Services: []string{"ServicoFiscal"}, Tasks: []string{"webPostoFiscalServer.exe"}},
	{Name: "webPostoLeituraAutomaçao", Services: []string{"ServicoAutomacao"}, Tasks: []string{"webPostoLeituraAutomacao.exe"}},
	{Name: "webPostoPayServer", Services: []string{"webPostoPayServer"}, Tasks: []string{"webPostoPaySW.exe"}},
	{Name: "webPostoPremmialntegracao", Services: []string{}, Tasks: []string{"webPostoPremiumIntegracao.exe"}},
}

// Settings armazena as configurações persistentes do usuário.
// Fiel ao SettingsManager do Python (settings_manager.py).
type Settings struct {
	LastFolder     string  `json:"last_folder"`
	AppearanceMode string  `json:"appearance_mode"` // "light", "dark", "system"
	UITheme        string  `json:"ui_theme"`        // "blue", "green"
	AutoUpdate     bool    `json:"auto_update"`
	FontSize       int     `json:"font_size"`
	ScanInterval   float64 `json:"scan_interval"`
	MaxViewLines   int     `json:"max_view_lines"`
}

// Manager lida com a leitura e escrita do arquivo de configurações.
type Manager struct {
	filePath string
}

func NewManager() *Manager {
	appdata := os.Getenv("APPDATA")
	if appdata == "" {
		appdata, _ = os.UserHomeDir()
	}
	path := filepath.Join(appdata, "LogFacil", "settings.json")
	return &Manager{filePath: path}
}

func (m *Manager) Load() (*Settings, error) {
	// Valores padrão idênticos ao Python _get_default_settings()
	s := &Settings{
		LastFolder:     DefaultRoot,
		AppearanceMode: "dark",
		UITheme:        "blue",
		AutoUpdate:     true,
		FontSize:       DefaultFontSize,
		ScanInterval:   DefaultScanInterval,
		MaxViewLines:   DefaultMaxViewLines,
	}

	data, err := os.ReadFile(m.filePath)
	if err != nil {
		if os.IsNotExist(err) {
			// Cria o arquivo inicial (como o Python faz no load())
			_ = m.Save(s)
			return s, nil
		}
		return nil, err
	}

	if err := json.Unmarshal(data, s); err != nil {
		return nil, err
	}

	return s, nil
}

func (m *Manager) Save(s *Settings) error {
	dir := filepath.Dir(m.filePath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}

	return os.WriteFile(m.filePath, data, 0644)
}
