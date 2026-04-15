package cmd

import (
	"fmt"
	"os"
	"path/filepath"
)

// ResolveScanRoot returns an absolute directory path for scanning.
// If positional is empty, uses the current working directory.
func ResolveScanRoot(positional string) (string, error) {
	if positional == "" {
		return os.Getwd()
	}
	abs, err := filepath.Abs(filepath.Clean(positional))
	if err != nil {
		return "", fmt.Errorf("resolve path: %w", err)
	}
	st, err := os.Stat(abs)
	if err != nil {
		return "", fmt.Errorf("stat %q: %w", abs, err)
	}
	if !st.IsDir() {
		return "", fmt.Errorf("%q is not a directory", abs)
	}
	return abs, nil
}

// ShortenRepoPath returns a display path relative to the current working directory.
func ShortenRepoPath(absPath string) string {
	cwd, err := os.Getwd()
	if err != nil {
		return filepath.ToSlash(absPath)
	}
	rel, err := filepath.Rel(cwd, absPath)
	if err != nil || rel == "." {
		return "."
	}
	return filepath.ToSlash(rel)
}
