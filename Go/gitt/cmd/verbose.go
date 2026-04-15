package cmd

import (
	"fmt"
	"os"
	"sync"
)

var verboseLogMu sync.Mutex

// Verbosef writes formatted text to stderr; safe for concurrent workers.
func Verbosef(format string, args ...any) {
	verboseLogMu.Lock()
	defer verboseLogMu.Unlock()
	fmt.Fprintf(os.Stderr, format, args...)
}
