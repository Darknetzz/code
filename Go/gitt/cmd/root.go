package cmd

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gitt/internal/version"
)

const appName = "gitt"

func Execute(args []string) error {
	if len(args) == 0 {
		printRootHelp()
		return nil
	}

	first := strings.ToLower(args[0])
	switch first {
	case "-h", "--help", "help":
		printRootHelp()
		return nil
	case "-v", "--version", "version":
		fmt.Println(version.String())
		return nil
	case "pull":
		return runPull(args[1:])
	default:
		return fmt.Errorf("%s: unknown command %q\n\n%s", appName, first, rootHelpText())
	}
}

func printRootHelp() {
	fmt.Print(rootHelpText())
}

func rootHelpText() string {
	prog := filepath.Base(os.Args[0])
	if prog == "" {
		prog = appName
	}
	return strings.TrimSpace(fmt.Sprintf(`
%s - recursive Git helper

Usage:
  %s <command> [options]

Commands:
  pull        Recursively pull repositories from current directory
  help        Show this help
  version     Show version information

Global flags:
  -h, --help       Show help
  -v, --version    Show version
`, appName, prog)) + "\n"
}

var errPullFailed = errors.New("one or more repositories failed")
