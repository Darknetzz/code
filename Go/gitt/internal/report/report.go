package report

import (
	"fmt"
	"io"
)

type Status string

const (
	StatusUpdated  Status = "updated"
	StatusUpToDate Status = "up-to-date"
	StatusSkipped  Status = "skipped"
	StatusFailed   Status = "failed"
	StatusFetched  Status = "fetched"
	StatusClean    Status = "clean"
	StatusDirty    Status = "dirty"
)

type RepoResult struct {
	Repo    string
	Status  Status
	Message string
}

type Summary struct {
	Updated  int
	UpToDate int
	Skipped  int
	Failed   int
	Fetched  int
	Clean    int
	Dirty    int
}

// SummaryMode selects which counters are printed in PrintSummary.
type SummaryMode int

const (
	SummaryModePull SummaryMode = iota
	SummaryModeFetch
	SummaryModeStatus
)

func (s *Summary) Add(status Status) {
	switch status {
	case StatusUpdated:
		s.Updated++
	case StatusUpToDate:
		s.UpToDate++
	case StatusSkipped:
		s.Skipped++
	case StatusFailed:
		s.Failed++
	case StatusFetched:
		s.Fetched++
	case StatusClean:
		s.Clean++
	case StatusDirty:
		s.Dirty++
	}
}

func PrintResult(w io.Writer, r RepoResult) {
	if r.Message == "" {
		fmt.Fprintf(w, "[%s] %s\n", r.Status, r.Repo)
		return
	}
	fmt.Fprintf(w, "[%s] %s: %s\n", r.Status, r.Repo, r.Message)
}

func PrintSummary(w io.Writer, s Summary, total int, mode SummaryMode) {
	fmt.Fprintln(w, "")
	fmt.Fprintf(w, "Scanned repos: %d\n", total)
	switch mode {
	case SummaryModePull:
		fmt.Fprintf(w, "Updated: %d\n", s.Updated)
		fmt.Fprintf(w, "Up-to-date: %d\n", s.UpToDate)
		fmt.Fprintf(w, "Skipped: %d\n", s.Skipped)
		fmt.Fprintf(w, "Failed: %d\n", s.Failed)
	case SummaryModeFetch:
		fmt.Fprintf(w, "Fetched: %d\n", s.Fetched)
		fmt.Fprintf(w, "Skipped: %d\n", s.Skipped)
		fmt.Fprintf(w, "Failed: %d\n", s.Failed)
	case SummaryModeStatus:
		fmt.Fprintf(w, "Clean: %d\n", s.Clean)
		fmt.Fprintf(w, "Dirty: %d\n", s.Dirty)
		fmt.Fprintf(w, "Skipped: %d\n", s.Skipped)
		fmt.Fprintf(w, "Failed: %d\n", s.Failed)
	}
}
