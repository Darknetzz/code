package gitops

import (
	"bytes"
	"fmt"
	"os/exec"
	"strings"
)

type Runner interface {
	Run(repoPath string, args ...string) (stdout string, stderr string, err error)
}

type ExecRunner struct{}

func (ExecRunner) Run(repoPath string, args ...string) (string, string, error) {
	cmdArgs := append([]string{"-C", repoPath}, args...)
	cmd := exec.Command("git", cmdArgs...)
	var outBuf bytes.Buffer
	var errBuf bytes.Buffer
	cmd.Stdout = &outBuf
	cmd.Stderr = &errBuf
	err := cmd.Run()
	return strings.TrimSpace(outBuf.String()), strings.TrimSpace(errBuf.String()), err
}

func IsRepo(r Runner, repoPath string) (bool, error) {
	out, errOut, err := r.Run(repoPath, "rev-parse", "--is-inside-work-tree")
	if err != nil {
		return false, fmt.Errorf("rev-parse failed: %w (%s)", err, chooseMessage(errOut, out))
	}
	return strings.EqualFold(strings.TrimSpace(out), "true"), nil
}

func IsDirty(r Runner, repoPath string) (bool, error) {
	out, errOut, err := r.Run(repoPath, "status", "--porcelain")
	if err != nil {
		return false, fmt.Errorf("status failed: %w (%s)", err, chooseMessage(errOut, out))
	}
	return strings.TrimSpace(out) != "", nil
}

func PullFFOnly(r Runner, repoPath string) (stdout string, stderr string, err error) {
	return r.Run(repoPath, "pull", "--ff-only")
}

func chooseMessage(primary, fallback string) string {
	if strings.TrimSpace(primary) != "" {
		return primary
	}
	return fallback
}
