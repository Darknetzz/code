package gitdiscovery

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDiscoverRepos_FindsGitDirAndGitFile(t *testing.T) {
	root := t.TempDir()

	repoA := filepath.Join(root, "repoA")
	repoB := filepath.Join(root, "nested", "repoB")
	if err := os.MkdirAll(filepath.Join(repoA, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir repoA: %v", err)
	}
	if err := os.MkdirAll(repoB, 0o755); err != nil {
		t.Fatalf("mkdir repoB: %v", err)
	}
	if err := os.WriteFile(filepath.Join(repoB, ".git"), []byte("gitdir: ../.git/modules/repoB"), 0o644); err != nil {
		t.Fatalf("write repoB .git file: %v", err)
	}

	repos, err := DiscoverRepos(DiscoverOptions{Root: root, MaxDepth: -1})
	if err != nil {
		t.Fatalf("discover repos: %v", err)
	}
	if len(repos) != 2 {
		t.Fatalf("expected 2 repos, got %d (%v)", len(repos), repos)
	}
}

func TestDiscoverRepos_RespectsMaxDepth(t *testing.T) {
	root := t.TempDir()
	repo := filepath.Join(root, "one", "two", "repo")
	if err := os.MkdirAll(filepath.Join(repo, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir repo: %v", err)
	}

	repos, err := DiscoverRepos(DiscoverOptions{Root: root, MaxDepth: 2})
	if err != nil {
		t.Fatalf("discover repos: %v", err)
	}
	if len(repos) != 0 {
		t.Fatalf("expected no repos due to depth limit, got %v", repos)
	}
}

func TestDiscoverRepos_HiddenDirectories(t *testing.T) {
	root := t.TempDir()
	hiddenRepo := filepath.Join(root, ".hiddenRepo")
	if err := os.MkdirAll(filepath.Join(hiddenRepo, ".git"), 0o755); err != nil {
		t.Fatalf("mkdir hidden repo: %v", err)
	}

	noHidden, err := DiscoverRepos(DiscoverOptions{Root: root, MaxDepth: -1, IncludeHidden: false})
	if err != nil {
		t.Fatalf("discover repos no hidden: %v", err)
	}
	if len(noHidden) != 0 {
		t.Fatalf("expected hidden repo to be skipped, got %v", noHidden)
	}

	withHidden, err := DiscoverRepos(DiscoverOptions{Root: root, MaxDepth: -1, IncludeHidden: true})
	if err != nil {
		t.Fatalf("discover repos with hidden: %v", err)
	}
	if len(withHidden) != 1 {
		t.Fatalf("expected hidden repo to be included, got %v", withHidden)
	}
}
