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
}

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
	}
}

func PrintResult(w io.Writer, r RepoResult) {
	if r.Message == "" {
		fmt.Fprintf(w, "[%s] %s\n", r.Status, r.Repo)
		return
	}
	fmt.Fprintf(w, "[%s] %s: %s\n", r.Status, r.Repo, r.Message)
}

func PrintSummary(w io.Writer, s Summary, total int) {
	fmt.Fprintln(w, "")
	fmt.Fprintf(w, "Scanned repos: %d\n", total)
	fmt.Fprintf(w, "Updated: %d\n", s.Updated)
	fmt.Fprintf(w, "Up-to-date: %d\n", s.UpToDate)
	fmt.Fprintf(w, "Skipped: %d\n", s.Skipped)
	fmt.Fprintf(w, "Failed: %d\n", s.Failed)
}
