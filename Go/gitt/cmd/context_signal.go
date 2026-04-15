package cmd

import (
	"context"
	"os"
	"os/signal"
	"syscall"
)

// RootCommandContext returns a context cancelled on Ctrl+C (interrupt) or SIGTERM.
func RootCommandContext() (context.Context, context.CancelFunc) {
	return signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
}
