// refreshenv loads User and Machine environment variables from the Windows
// registry into the current process and spawns a new shell that inherits them.
// Build: go build -o refreshenv.exe .
package main

import (
	"flag"
	"fmt"
	"os"
	"os/exec"
	"strings"

	"golang.org/x/sys/windows/registry"
)

const (
	envKeyMachine = `SYSTEM\CurrentControlSet\Control\Session Manager\Environment`
	envKeyUser    = `Environment`
)

func main() {
	spawnShell := flag.Bool("shell", true, "spawn a new shell with refreshed env (default true)")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintln(os.Stderr, "Refreshes process environment from User and Machine registry,")
		fmt.Fprintln(os.Stderr, "then spawns a new cmd.exe so that shell has the updated env.")
		fmt.Fprintln(os.Stderr, "Options:")
		flag.PrintDefaults()
	}
	flag.Parse()

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

	// Apply to current process
	for name, val := range vars {
		os.Setenv(name, val)
	}

	if !*spawnShell {
		fmt.Println("Environment refreshed. (Run with -shell=true to spawn a new shell with this env.)")
		return
	}

	cmd := exec.Command("cmd.exe", "/K")
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Env = os.Environ()
	if err := cmd.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "refreshenv: %v\n", err)
		os.Exit(1)
	}
}
