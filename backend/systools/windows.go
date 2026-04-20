package systools

import (
	"fmt"
	"net"
	"os"
	"os/exec"
	"strings"
	"syscall"

	"golang.org/x/sys/windows"
)

// IsAdmin verifica se o processo atual possui privilégios administrativos.
// Idêntico ao is_admin() do Python (core/os_services.py).
func IsAdmin() bool {
	var sid *windows.SID
	err := windows.AllocateAndInitializeSid(
		&windows.SECURITY_NT_AUTHORITY,
		2,
		windows.SECURITY_BUILTIN_DOMAIN_RID,
		windows.DOMAIN_ALIAS_RID_ADMINS,
		0, 0, 0, 0, 0, 0,
		&sid,
	)
	if err != nil {
		return false
	}
	defer windows.FreeSid(sid)

	token := windows.Token(0)
	member, err := token.IsMember(sid)
	if err != nil {
		return false
	}
	return member
}

// RunAsAdmin reinicia o processo atual solicitando elevação de privilégios.
// Idêntico ao run_as_admin() do Python (core/os_services.py).
func RunAsAdmin() error {
	verb := "runas"
	exe, err := os.Executable()
	if err != nil {
		return err
	}
	cwd, _ := os.Getwd()
	args := os.Args[1:]

	verbPtr, _ := syscall.UTF16PtrFromString(verb)
	exePtr, _ := syscall.UTF16PtrFromString(exe)
	cwdPtr, _ := syscall.UTF16PtrFromString(cwd)

	var argString string
	for _, arg := range args {
		argString += fmt.Sprintf("\"%s\" ", arg)
	}
	argPtr, _ := syscall.UTF16PtrFromString(argString)

	var showCmd int32 = 1 // SW_SHOWNORMAL
	return windows.ShellExecute(0, verbPtr, exePtr, argPtr, cwdPtr, showCmd)
}

// CheckServiceStatus retorna se o serviço existe e se está rodando.
// Retorna: (existe, rodando, mensagem)
// Idêntico ao check_service_status() do Python (core/os_services.py).
func CheckServiceStatus(serviceName string) (bool, bool, string) {
	cmd := exec.Command("sc", "query", serviceName)
	cmd.SysProcAttr = &windows.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()

	strOutput := string(output)

	// Serviço não existe — verifica pelo código de erro 1060 ou mensagens conhecidas
	if err != nil {
		lower := strings.ToLower(strOutput)
		if strings.Contains(lower, "não existe") ||
			strings.Contains(lower, "does not exist") ||
			strings.Contains(strOutput, "1060") {
			return false, false, fmt.Sprintf("Serviço '%s' não instalado", serviceName)
		}
		return false, false, fmt.Sprintf("Erro ao verificar '%s'", serviceName)
	}

	// Verificação apenas por palavras completas (evita falso positivo com "4" e "1")
	upperOutput := strings.ToUpper(strOutput)
	if strings.Contains(upperOutput, "RUNNING") {
		return true, true, fmt.Sprintf("Serviço '%s' em execução", serviceName)
	} else if strings.Contains(upperOutput, "STOPPED") {
		return true, false, fmt.Sprintf("Serviço '%s' parado", serviceName)
	}

	return true, false, fmt.Sprintf("Serviço '%s' status desconhecido", serviceName)
}

// StopWindowsService para um serviço do Windows.
// Idêntico ao stop_windows_service() do Python (core/os_services.py).
func StopWindowsService(serviceName string) (bool, string) {
	cmd := exec.Command("net", "stop", serviceName)
	cmd.SysProcAttr = &windows.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()

	outStr := strings.ToLower(string(output))
	if err == nil {
		return true, fmt.Sprintf("Serviço '%s' parado", serviceName)
	}

	if strings.Contains(outStr, "não está iniciado") || strings.Contains(outStr, "not started") {
		return true, fmt.Sprintf("Serviço '%s' já estava parado", serviceName)
	}
	if strings.Contains(outStr, "acesso negado") || strings.Contains(outStr, "access denied") {
		return false, fmt.Sprintf("Acesso negado ao parar '%s'", serviceName)
	}

	return false, string(output)
}

// StartWindowsService inicia um serviço do Windows.
// Idêntico ao start_windows_service() do Python (core/os_services.py).
func StartWindowsService(serviceName string) (bool, string) {
	cmd := exec.Command("net", "start", serviceName)
	cmd.SysProcAttr = &windows.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()

	outStr := strings.ToLower(string(output))
	if err == nil {
		return true, fmt.Sprintf("Serviço '%s' iniciado", serviceName)
	}

	if strings.Contains(outStr, "já foi iniciado") || strings.Contains(outStr, "already been started") {
		return true, fmt.Sprintf("Serviço '%s' já estava em execução", serviceName)
	}
	if strings.Contains(outStr, "acesso negado") || strings.Contains(outStr, "access denied") {
		return false, fmt.Sprintf("Acesso negado ao iniciar '%s'", serviceName)
	}

	return false, string(output)
}

// KillTask encerra um processo pelo nome da imagem.
// Idêntico ao kill_task() do Python (core/os_services.py).
func KillTask(taskName string) (bool, string) {
	cmd := exec.Command("taskkill", "/F", "/IM", taskName)
	cmd.SysProcAttr = &windows.SysProcAttr{HideWindow: true}
	output, err := cmd.CombinedOutput()

	outStr := strings.ToLower(string(output))
	if err == nil {
		return true, fmt.Sprintf("Processo '%s' finalizado", taskName)
	}

	if strings.Contains(outStr, "não encontrado") || strings.Contains(outStr, "not found") {
		return true, fmt.Sprintf("Processo '%s' não encontrado", taskName)
	}
	if strings.Contains(outStr, "acesso negado") || strings.Contains(outStr, "access denied") {
		return false, fmt.Sprintf("Acesso negado ao encerrar '%s'", taskName)
	}

	return false, string(output)
}

// GetMainIP retorna o IP principal da máquina (interface de rede ativa).
// Idêntico ao get_main_ip() do Python (core/utils.py).
func GetMainIP() string {
	// Tenta descobrir a interface de saída conectando a um IP externo (não envia dados)
	conn, err := net.Dial("udp", "8.8.8.8:80")
	if err == nil {
		defer conn.Close()
		localAddr := conn.LocalAddr().(*net.UDPAddr)
		return localAddr.IP.String()
	}

	// Fallback: hostname
	addrs, err := net.InterfaceAddrs()
	if err == nil {
		for _, addr := range addrs {
			if ipnet, ok := addr.(*net.IPNet); ok && !ipnet.IP.IsLoopback() {
				if ipnet.IP.To4() != nil {
					return ipnet.IP.String()
				}
			}
		}
	}

	return "127.0.0.1"
}
