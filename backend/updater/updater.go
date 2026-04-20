package updater

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type Release struct {
	TagName string  `json:"tag_name"`
	Body    string  `json:"body"`
	Assets  []Asset `json:"assets"`
}

type Asset struct {
	Name               string `json:"name"`
	BrowserDownloadUrl string `json:"browser_download_url"`
}

type UpdateResponse struct {
	HasUpdate    bool   `json:"has_update"`
	Version      string `json:"version"`
	DownloadUrl  string `json:"download_url"`
	ReleaseNotes string `json:"release_notes"`
	Message      string `json:"message"`
}

// CheckForUpdates consulta a API do GitHub
func CheckForUpdates(repo, currentVersion string) UpdateResponse {
	url := fmt.Sprintf("https://api.github.com/repos/%s/releases/latest", repo)

	client := http.Client{Timeout: 10 * time.Second}
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return UpdateResponse{Message: "Erro ao criar requisição"}
	}
	req.Header.Set("Accept", "application/vnd.github.v3+json")

	resp, err := client.Do(req)
	if err != nil {
		return UpdateResponse{Message: "Falha na conexão com servidor: " + err.Error()}
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return UpdateResponse{Message: fmt.Sprintf("Erro na API do GitHub: status %d", resp.StatusCode)}
	}

	var release Release
	if err := json.NewDecoder(resp.Body).Decode(&release); err != nil {
		return UpdateResponse{Message: "Erro ao decodificar pacote do GitHub"}
	}

	latestVersion := strings.TrimPrefix(release.TagName, "v")
	currentVersionClean := strings.TrimSpace(strings.ToLower(strings.TrimPrefix(currentVersion, "v")))

	// Remove suffix "-GO" for safe semver compare if exists
	currentVersionClean = strings.Split(currentVersionClean, "-")[0]
	latestVersionClean := strings.Split(strings.ToLower(latestVersion), "-")[0]

	hasUpdate := isNewer(latestVersionClean, currentVersionClean)

	if !hasUpdate {
		return UpdateResponse{HasUpdate: false, Message: "LogFácil está atualizado!"}
	}

	var exeUrl string
	for _, a := range release.Assets {
		if strings.HasSuffix(strings.ToLower(a.Name), ".exe") {
			exeUrl = a.BrowserDownloadUrl
			break
		}
	}

	if exeUrl == "" {
		return UpdateResponse{Message: "Novo executável não encontrado nesta versão."}
	}

	return UpdateResponse{
		HasUpdate:    true,
		Version:      latestVersion,
		ReleaseNotes: release.Body,
		DownloadUrl:  exeUrl,
	}
}

// ProgressWriter conta os bytes e dispara evento Wails de progresso
type ProgressWriter struct {
	ctx          context.Context
	total        int64
	downloaded   int64
	lastReported int
	updateChan   chan struct{} // garante updates frequentes
}

func (pw *ProgressWriter) Write(p []byte) (int, error) {
	n := len(p)
	pw.downloaded += int64(n)

	if pw.total > 0 {
		percent := int((float64(pw.downloaded) / float64(pw.total)) * 100)
		if percent > pw.lastReported {
			pw.lastReported = percent
			runtime.EventsEmit(pw.ctx, "update-progress", map[string]interface{}{
				"percent":    percent,
				"downloaded": pw.downloaded,
				"total":      pw.total,
			})
		}
	} else {
		// Sem cabecalho de tamanho, emite bytes de 0 a 100 random ou só o valor
		runtime.EventsEmit(pw.ctx, "update-progress", map[string]interface{}{
			"percent":    50, // indeterminante
			"downloaded": pw.downloaded,
			"total":      0,
		})
	}
	return n, nil
}

// DownloadUpdate salva o executável em C:\temp
func DownloadUpdate(ctx context.Context, downloadUrl string) (string, error) {
	tempPath := filepath.Join("C:\\", "temp")
	os.MkdirAll(tempPath, 0755) // Força criação da C:\temp

	fileName := "LogFacil_Update.exe"
	filePath := filepath.Join(tempPath, fileName)

	// Inicia download
	client := http.Client{Timeout: 5 * time.Minute}
	resp, err := client.Get(downloadUrl)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("Erro HTTP: status %d", resp.StatusCode)
	}

	out, err := os.Create(filePath)
	if err != nil {
		return "", fmt.Errorf("Falha ao criar arquivo: %v", err)
	}
	defer out.Close()

	totalSize, _ := strconv.ParseInt(resp.Header.Get("Content-Length"), 10, 64)

	writer := &ProgressWriter{
		ctx:   ctx,
		total: totalSize,
	}

	// Cópia passando pelo writer que emite os eventos
	_, err = io.Copy(out, io.TeeReader(resp.Body, writer))
	if err != nil {
		return "", err
	}

	// Verifica se arquivo tem um tamanho razoável (> 3MB)
	stat, err := os.Stat(filePath)
	if err != nil || stat.Size() < 3*1024*1024 {
		os.Remove(filePath)
		return "", fmt.Errorf("Arquivo baixado parece inválido (muito pequeno).")
	}

	return filePath, nil
}

// InstallUpdate cria e engatilha o bat para reabrir blindado
func InstallUpdate(appPath, downloadedFile string) error {
	exeName := filepath.Base(appPath)

	batContent := fmt.Sprintf(`@echo off
echo Atualizando o LogFacil... 
timeout /t 3 /nobreak > NUL

:: Tenta forcar encerramento caso ainda esteja rodando
taskkill /F /IM "%[1]s" > NUL 2>&1

:: Desbloqueia o arquivo (Remove flag de Web do Windows)
powershell -Command "Unblock-File -Path '%[2]s'" > NUL 2>&1

:: Deletar backup antigo se existir
if exist "%[3]s.bak" del /F /Q "%[3]s.bak" > NUL 2>&1

:: Renomear atual para backup
if exist "%[3]s" ren "%[3]s" "%[1]s.bak" > NUL 2>&1

:: Copiar o novo arquivo baixado
copy /Y "%[2]s" "%[3]s" > NUL

:: Deletar arquivo temporario do Update
del /F /Q "%[2]s" > NUL 2>&1

:: Deleta o backup 
if exist "%[3]s.bak" del /F /Q "%[3]s.bak" > NUL 2>&1

:: Inicia o novo aplicativo de forma independente
start "" "%[3]s"

:: Se auto deletar
del /F /Q "%%~f0"
`, exeName, downloadedFile, appPath)

	tempDir := filepath.Join("C:\\", "temp")
	batPath := filepath.Join(tempDir, fmt.Sprintf("logfacil_updater_%d.bat", os.Getpid()))

	err := os.WriteFile(batPath, []byte(batContent), 0666)
	if err != nil {
		return fmt.Errorf("Falha ao criar script updater (.bat): %v", err)
	}

	// Executa o .bat ocultando a janela
	cmd := exec.Command("cmd.exe", "/C", batPath)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}

	err = cmd.Start()
	if err != nil {
		return fmt.Errorf("Falha ao engatilhar bat: %v", err)
	}

	return nil
}

func isNewer(latest, current string) bool {
	lParts := parseVersion(latest)
	cParts := parseVersion(current)

	for len(lParts) < 3 {
		lParts = append(lParts, 0)
	}
	for len(cParts) < 3 {
		cParts = append(cParts, 0)
	}

	for i := range lParts {
		if lParts[i] > cParts[i] {
			return true
		}
		if lParts[i] < cParts[i] {
			return false
		}
	}
	return false
}

func parseVersion(v string) []int {
	parts := strings.Split(v, ".")
	nums := make([]int, 0, len(parts))
	for _, p := range parts {
		n, _ := strconv.Atoi(strings.TrimSpace(p))
		nums = append(nums, n)
	}
	return nums
}
