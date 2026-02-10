// refreshenv loads User and Machine environment variables from the Windows
// registry into the current process and spawns a new shell that inherits them.
// Build: go build -o refreshenv.exe .
package main

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"

	"golang.org/x/sys/windows/registry"
)

const (
	envKeyMachine = `SYSTEM\CurrentControlSet\Control\Session Manager\Environment`
	envKeyUser    = `Environment`
)

func main() {
	spawnShell := flag.Bool("shell", true, "spawn a new shell with refreshed env (default true)")
	usePowerShell := flag.Bool("pwsh", false, "spawn PowerShell instead of cmd (default: auto when run from PowerShell)")
	emit := flag.Bool("emit", false, "print shell commands to stdout for current shell to eval (e.g. refreshenv -emit | iex)")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintln(os.Stderr, "Refreshes process environment from User and Machine registry,")
		fmt.Fprintln(os.Stderr, "then spawns a new shell (PowerShell or cmd) that has the updated env.")
		fmt.Fprintln(os.Stderr, "Use -emit to output commands for the current shell instead (e.g. refreshenv -emit | iex).")
		fmt.Fprintln(os.Stderr, "Options:")
		flag.PrintDefaults()
	}
	flag.Parse()

	// Resolve shell paths before we overwrite Path (refreshed Path may not include System32)
	systemRoot := os.Getenv("SystemRoot")
	if systemRoot == "" {
		systemRoot = "C:\\Windows"
	}
	cmdExe := filepath.Join(systemRoot, "System32", "cmd.exe")
	psExe := filepath.Join(systemRoot, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")

	vars := make(map[string]string)

	// User first, then Machine (Machine overwrites User for same name, like PowerShell)
	for _, pair := range []struct {
		k    registry.Key
		path string
	}{
		{registry.CURRENT_USER, envKeyUser},
		{registry.LOCAL_MACHINE, envKeyMachine},
	} {
		key, err := registry.OpenKey(pair.k, pair.path, registry.READ)
		if err != nil {
			continue
		}
		names, err := key.ReadValueNames(0)
		if err != nil {
			key.Close()
			continue
		}
		for _, name := range names {
			if name == "Path" {
				continue
			}
			s, _, err := key.GetStringValue(name)
			if err != nil {
				continue
			}
			vars[name] = s
		}
		key.Close()
	}

	// Path: Machine + User (semicolon-separated)
	var pathMachine, pathUser string
	if k, err := registry.OpenKey(registry.LOCAL_MACHINE, envKeyMachine, registry.READ); err == nil {
		pathMachine, _, _ = k.GetStringValue("Path")
		k.Close()
	}
	if k, err := registry.OpenKey(registry.CURRENT_USER, envKeyUser, registry.READ); err == nil {
		pathUser, _, _ = k.GetStringValue("Path")
		k.Close()
	}
	pathCombined := strings.Trim(strings.TrimSuffix(pathMachine, ";")+";"+strings.TrimSuffix(pathUser, ";"), ";")
	if pathCombined != "" {
		vars["Path"] = pathCombined
	}

	// -emit: output commands for current shell to eval (so parent gets refreshed env)
	if *emit {
		usePS := *usePowerShell || os.Getenv("PSModulePath") != ""
		for name, val := range vars {
			if usePS {
				escaped := strings.ReplaceAll(val, "'", "''")
				fmt.Printf("$env:%s = '%s'; ", name, escaped)
			} else {
				escaped := strings.ReplaceAll(val, `"`, `""`)
				fmt.Printf("set \"%s=%s\"\n", name, escaped)
			}
		}
		if usePS {
			fmt.Println()
		}
		return
	}

	// Apply to current process
	for name, val := range vars {
		os.Setenv(name, val)
	}

	if !*spawnShell {
		fmt.Println("Environment refreshed. (Run with -shell=true to spawn a new shell with this env.)")
		return
	}

	fmt.Println("Environment refreshed from registry. Spawning new shell in a new window...")
	// Use PowerShell when -pwsh or when we're likely in PowerShell (e.g. PSModulePath set)
	usePS := *usePowerShell || os.Getenv("PSModulePath") != ""
	shellPath := cmdExe
	shellArgs := []string{"/K"}
	if usePS {
		// Prefer pwsh (PowerShell 7) if in refreshed PATH, else Windows PowerShell 5.1
		if path, err := exec.LookPath("pwsh"); err == nil {
			shellPath = path
			shellArgs = []string{"-NoExit"}
		} else if _, err := os.Stat(psExe); err == nil {
			shellPath = psExe
			shellArgs = []string{"-NoExit"}
		} else {
			shellPath = cmdExe
			shellArgs = []string{"/K"}
		}
	}

	cmd := exec.Command(shellPath, shellArgs...)
	cmd.Env = os.Environ()
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x10} // CREATE_NEW_CONSOLE: new window, no nesting
	if err := cmd.Start(); err != nil {
		fmt.Fprintf(os.Stderr, "refreshenv: %v\n", err)
		os.Exit(1)
	}
	// Exit so the current shell gets its prompt back; new shell runs in its own window
}
