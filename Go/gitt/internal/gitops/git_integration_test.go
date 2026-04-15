package gitops

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestPullFFOnly_Integration(t *testing.T) {
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("git not available")
	}

	root := t.TempDir()
	remote := filepath.Join(root, "remote.git")
	seed := filepath.Join(root, "seed")
	clone := filepath.Join(root, "clone")

	mustRun(t, root, "git", "init", "--bare", remote)
	mustRun(t, root, "git", "clone", remote, seed)
	mustRun(t, seed, "git", "config", "user.email", "gitt-test@example.com")
	mustRun(t, seed, "git", "config", "user.name", "gitt-test")
	mustWriteFile(t, filepath.Join(seed, "README.md"), []byte("hello\n"))
	mustRun(t, seed, "git", "add", "README.md")
	mustRun(t, seed, "git", "commit", "-m", "seed commit")
	mustRun(t, seed, "git", "push", "origin", "HEAD")

	mustRun(t, root, "git", "clone", remote, clone)
	mustWriteFile(t, filepath.Join(seed, "README.md"), []byte("hello again\n"))
	mustRun(t, seed, "git", "add", "README.md")
	mustRun(t, seed, "git", "commit", "-m", "update commit")
	mustRun(t, seed, "git", "push", "origin", "HEAD")

	runner := ExecRunner{}
	stdout, stderr, err := PullFFOnly(context.Background(), runner, clone)
	if err != nil {
		t.Fatalf("pull ff-only failed: %v (stdout=%q stderr=%q)", err, stdout, stderr)
	}

	content, err := os.ReadFile(filepath.Join(clone, "README.md"))
	if err != nil {
		t.Fatalf("read clone file: %v", err)
	}
	if string(content) != "hello again\n" {
		t.Fatalf("unexpected file content after pull: %q", string(content))
	}
}

func mustRun(t *testing.T, dir string, name string, args ...string) {
	t.Helper()
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("command failed: %s %v: %v\n%s", name, args, err, string(out))
	}
}

func mustWriteFile(t *testing.T, path string, data []byte) {
	t.Helper()
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write file %s: %v", path, err)
	}
}
