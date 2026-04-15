package cmd

import (
	"errors"
	"strings"
	"testing"

	"gitt/internal/report"
)

type fakeResponse struct {
	stdout string
	stderr string
	err    error
}

type fakeRunner struct {
	responses map[string]fakeResponse
}

func (f fakeRunner) Run(repoPath string, args ...string) (string, string, error) {
	key := repoPath + "|" + strings.Join(args, " ")
	resp, ok := f.responses[key]
	if !ok {
		return "", "missing fake response", errors.New("missing fake response")
	}
	return resp.stdout, resp.stderr, resp.err
}

func TestIsUpToDate(t *testing.T) {
	if !isUpToDate("Already up to date.", "") {
		t.Fatalf("expected true for up to date stdout")
	}
	if !isUpToDate("", "Already up-to-date.") {
		t.Fatalf("expected true for up-to-date stderr")
	}
	if isUpToDate("Fast-forward", "") {
		t.Fatalf("expected false for update output")
	}
}

func TestPullOneRepo_DryRun(t *testing.T) {
	runner := fakeRunner{
		responses: map[string]fakeResponse{
			"/tmp/repo|rev-parse --is-inside-work-tree": {stdout: "true"},
			"/tmp/repo|status --porcelain":              {stdout: ""},
		},
	}
	result := pullOneRepo("/tmp/repo", pullOptions{dryRun: true}, runner)
	if result.Status != report.StatusSkipped {
		t.Fatalf("expected skipped, got %s", result.Status)
	}
}

func TestPullOneRepo_Updated(t *testing.T) {
	runner := fakeRunner{
		responses: map[string]fakeResponse{
			"/tmp/repo|rev-parse --is-inside-work-tree": {stdout: "true"},
			"/tmp/repo|status --porcelain":              {stdout: ""},
			"/tmp/repo|pull --ff-only":                  {stdout: "Fast-forward"},
		},
	}
	result := pullOneRepo("/tmp/repo", pullOptions{}, runner)
	if result.Status != report.StatusUpdated {
		t.Fatalf("expected updated, got %s", result.Status)
	}
}

func TestPullOneRepo_UpToDate(t *testing.T) {
	runner := fakeRunner{
		responses: map[string]fakeResponse{
			"/tmp/repo|rev-parse --is-inside-work-tree": {stdout: "true"},
			"/tmp/repo|status --porcelain":              {stdout: ""},
			"/tmp/repo|pull --ff-only":                  {stderr: "Already up to date."},
		},
	}
	result := pullOneRepo("/tmp/repo", pullOptions{}, runner)
	if result.Status != report.StatusUpToDate {
		t.Fatalf("expected up-to-date, got %s", result.Status)
	}
}

func TestPullOneRepo_DirtySkipped(t *testing.T) {
	runner := fakeRunner{
		responses: map[string]fakeResponse{
			"/tmp/repo|rev-parse --is-inside-work-tree": {stdout: "true"},
			"/tmp/repo|status --porcelain":              {stdout: " M file.txt"},
		},
	}
	result := pullOneRepo("/tmp/repo", pullOptions{}, runner)
	if result.Status != report.StatusSkipped {
		t.Fatalf("expected skipped for dirty repo, got %s", result.Status)
	}
}
