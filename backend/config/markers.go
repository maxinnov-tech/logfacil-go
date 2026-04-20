package config

// LogLevel define a severidade da linha para fim de pesos e estilos CSS (como negrito)
type LogLevel string

const (
	LevelException LogLevel = "exception"
	LevelError     LogLevel = "error"
	LevelWarn      LogLevel = "warn"
	LevelInfo      LogLevel = "info"
	LevelDebug     LogLevel = "debug"
)

// LogMarker mapeia um termo de busca a um nível de severidade e uma cor.
// As alterações aqui refletem no frontend (App.vue) no Terminal e no Minimap.
type LogMarker struct {
	Pattern string   `json:"pattern"`
	Level   LogLevel `json:"level"`
	Color   string   `json:"color"` // Recebe uma das constantes de cor abaixo
}

// Cores do Sistema (Centralizadas)
// Mude aqui para alterar todas as ocorrências de um nível de log de uma vez
const (
	ColorException = "#ff6b6b" // Vermelho Forte (Negrito)
	ColorError     = "#ff6b6b" // Vermelho
	ColorWarn      = "#ffd93d" // Amarelo
	ColorWarnAlt   = "#ffba08" // Amarelo Escuro / Ouro
	ColorInfo      = "#6bc167" // Verde
	ColorDebug     = "#868e96" // Cinza
)

// DefaultMarkers centraliza todos os erros mapeados do sistema.
// É aqui que você adiciona novos termos para serem identificados.
var DefaultMarkers = []LogMarker{
	// Erros Críticos
	{Pattern: "EXCEPTION", Level: LevelException, Color: ColorException},
	{Pattern: "RETORNO: 500", Level: LevelException, Color: ColorException},
	{Pattern: "FATAL", Level: LevelError, Color: ColorError},
	{Pattern: "ERROR", Level: LevelError, Color: ColorError},
	{Pattern: "FALHA", Level: LevelError, Color: ColorError},
	{Pattern: "EListError Erro: Duplicates not allowed", Level: LevelError, Color: ColorError},

	// Avisos
	{Pattern: "WARN", Level: LevelWarn, Color: ColorWarn},
	{Pattern: "ATENÇÃO", Level: LevelWarn, Color: ColorWarn},
	{Pattern: "RETORNO: 404", Level: LevelWarn, Color: ColorWarnAlt},

	// Informativos
	{Pattern: "INFO", Level: LevelInfo, Color: ColorInfo},

	// Debug
	{Pattern: "DEBUG", Level: LevelDebug, Color: ColorDebug},
}
