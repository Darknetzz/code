package cmd

import (
	"flag"
	"fmt"
	"os"
)

// ScanFlags holds common directory discovery options shared by subcommands.
type ScanFlags struct {
	MaxDepth      int
	IncludeHidden bool
	Jobs          int
	Verbose       bool
}

// RegisterScanFlags adds --max-depth, --include-hidden, --jobs, --verbose to fs.
func RegisterScanFlags(fs *flag.FlagSet, opts *ScanFlags, defaultJobs int) {
	fs.IntVar(&opts.MaxDepth, "max-depth", -1, "max directory depth to scan (-1 for unlimited)")
	fs.BoolVar(&opts.IncludeHidden, "include-hidden", false, "include hidden directories while scanning")
	fs.IntVar(&opts.Jobs, "jobs", defaultJobs, "number of repositories processed in parallel")
	fs.BoolVar(&opts.Verbose, "verbose", false, "print extra details while running")
}

// ValidateScanFlags returns an error if jobs < 1.
func ValidateScanFlags(cmd string, opts ScanFlags) error {
	if opts.Jobs < 1 {
		return fmt.Errorf("%s: --jobs must be >= 1", cmd)
	}
	return nil
}

// SetFlagSetOutput sets stderr and a minimal Usage wrapper for a subcommand.
func SetFlagSetOutput(fs *flag.FlagSet, usageLine string) {
	fs.SetOutput(os.Stderr)
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "%s\n\n", usageLine)
		fs.PrintDefaults()
	}
}
