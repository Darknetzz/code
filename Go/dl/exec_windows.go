//go:build windows

package main

import "fmt"

func syscallExec(argv0 string, argv []string, envv []string) error {
	return fmt.Errorf("exec not supported on windows")
}
