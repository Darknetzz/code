package cmd

import (
	"context"
	"errors"
	"testing"

	"gitt/internal/report"
)

type fakeResponse struct {
	stdout string
	stderr string
	err    error
}

type fakeRunner struct {
	queue []fakeResponse
}

func (f *fakeRunner) Run(ctx context.Context, repoPath string, args ...string) (string, string, error) {
	_ = ctx
	_ = repoPath
	if len(f.queue) == 0 {
		return "", "no more fake responses", errors.New("no more fake responses")
	}
	r := f.queue[0]
	f.queue = f.queue[1:]
	return r.stdout, r.stderr, r.err
}

func TestPullOneRepo_DryRun(t *testing.T) {
	runner := &fakeRunner{
		queue: []fakeResponse{
			{stdout: "true"},
			{stdout: ""},
		},
	}
	ctx := context.Background()
	result := pullOneRepo(ctx, "/tmp/repo", pullOptions{dryRun: true, ScanFlags: ScanFlags{}}, runner)
	if result.Status != report.StatusSkipped {
		t.Fatalf("expected skipped, got %s", result.Status)
	}
}

func TestPullOneRepo_Updated(t *testing.T) {
	runner := &fakeRunner{
		queue: []fakeResponse{
			{stdout: "true"},
			{stdout: ""},
			{stdout: "aaa"},
			{stdout: "Fast-forward"},
			{stdout: "bbb"},
		},
	}
	ctx := context.Background()
	result := pullOneRepo(ctx, "/tmp/repo", pullOptions{ScanFlags: ScanFlags{}}, runner)
	if result.Status != report.StatusUpdated {
		t.Fatalf("expected updated, got %s", result.Status)
	}
}

func TestPullOneRepo_UpToDate(t *testing.T) {
	runner := &fakeRunner{
		queue: []fakeResponse{
			{stdout: "true"},
			{stdout: ""},
			{stdout: "samehash"},
			{stderr: "Already up to date."}, // localized message ignored for classification
			{stdout: "samehash"},
		},
	}
	ctx := context.Background()
	result := pullOneRepo(ctx, "/tmp/repo", pullOptions{ScanFlags: ScanFlags{}}, runner)
	if result.Status != report.StatusUpToDate {
		t.Fatalf("expected up-to-date, got %s", result.Status)
	}
}

func TestPullOneRepo_DirtySkipped(t *testing.T) {
	runner := &fakeRunner{
		queue: []fakeResponse{
			{stdout: "true"},
			{stdout: " M file.txt"},
		},
	}
	ctx := context.Background()
	result := pullOneRepo(ctx, "/tmp/repo", pullOptions{ScanFlags: ScanFlags{}}, runner)
	if result.Status != report.StatusSkipped {
		t.Fatalf("expected skipped for dirty repo, got %s", result.Status)
	}
}
