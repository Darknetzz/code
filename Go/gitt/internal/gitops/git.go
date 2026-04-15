package gitops

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// Runner runs git commands in a repository directory.
type Runner interface {
	Run(ctx context.Context, repoPath string, args ...string) (stdout string, stderr string, err error)
}

// ExecRunner runs real git on PATH.
type ExecRunner struct{}

func (ExecRunner) Run(ctx context.Context, repoPath string, args ...string) (string, string, error) {
	cmdArgs := append([]string{"-C", repoPath}, args...)
	cmd := exec.CommandContext(ctx, "git", cmdArgs...)
	cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
	var outBuf bytes.Buffer
	var errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err := cmd.Run()
	return strings.TrimSpace(outBuf.String()), strings.TrimSpace(errBuf.String()), err
}

func IsRepo(ctx context.Context, r Runner, repoPath string) (bool, error) {
	out, errOut, err := r.Run(ctx, repoPath, "rev-parse", "--is-inside-work-tree")
	if err != nil {
		return false, fmt.Errorf("rev-parse failed: %w (%s)", err, chooseMessage(errOut, out))
	}
	return strings.EqualFold(strings.TrimSpace(out), "true"), nil
}

func IsDirty(ctx context.Context, r Runner, repoPath string) (bool, error) {
	out, errOut, err := r.Run(ctx, repoPath, "status", "--porcelain")
	if err != nil {
		return false, fmt.Errorf("status failed: %w (%s)", err, chooseMessage(errOut, out))
	}
	return strings.TrimSpace(out) != "", nil
}

// RevParse returns the full object name for rev (e.g. "HEAD").
func RevParse(ctx context.Context, r Runner, repoPath, rev string) (string, error) {
	out, errOut, err := r.Run(ctx, repoPath, "rev-parse", rev)
	if err != nil {
		return "", fmt.Errorf("rev-parse %s failed: %w (%s)", rev, err, chooseMessage(errOut, out))
	}
	return strings.TrimSpace(out), nil
}

func PullFFOnly(ctx context.Context, r Runner, repoPath string) (stdout string, stderr string, err error) {
	return r.Run(ctx, repoPath, "pull", "--ff-only")
}

// FetchPrune runs git fetch --prune in repoPath.
func FetchPrune(ctx context.Context, r Runner, repoPath string) (stdout string, stderr string, err error) {
	return r.Run(ctx, repoPath, "fetch", "--prune")
}

// StatusPorcelain returns raw porcelain status output (may be empty if clean).
func StatusPorcelain(ctx context.Context, r Runner, repoPath string) (string, error) {
	out, errOut, err := r.Run(ctx, repoPath, "status", "--porcelain")
	if err != nil {
		return "", fmt.Errorf("status failed: %w (%s)", err, chooseMessage(errOut, out))
	}
	return out, nil
}

func chooseMessage(primary, fallback string) string {
	if strings.TrimSpace(primary) != "" {
		return primary
	}
	return fallback
}
