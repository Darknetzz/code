package gitdiscovery

import (
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type DiscoverOptions struct {
	Root          string
	MaxDepth      int
	IncludeHidden bool
}

var defaultSkipDirs = map[string]struct{}{
	".git":         {},
	"node_modules": {},
	".venv":        {},
	"venv":         {},
	".idea":        {},
	".vscode":      {},
}

func DiscoverRepos(opts DiscoverOptions) ([]string, error) {
	root := filepath.Clean(opts.Root)
	repos := make([]string, 0, 16)

	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return nil
		}

		if !d.IsDir() {
			return nil
		}

		if path != root && shouldSkipDir(path, d.Name(), root, opts) {
			return filepath.SkipDir
		}

		gitPath := filepath.Join(path, ".git")
		if exists(gitPath) {
			repos = append(repos, path)
		}

		return nil
	})
	if err != nil {
		return nil, err
	}

	sort.Strings(repos)
	return repos, nil
}

func shouldSkipDir(path, name, root string, opts DiscoverOptions) bool {
	if _, ok := defaultSkipDirs[name]; ok {
		return true
	}

	if !opts.IncludeHidden && strings.HasPrefix(name, ".") {
		return true
	}

	if opts.MaxDepth >= 0 && depthFromRoot(root, path) > opts.MaxDepth {
		return true
	}

	return false
}

func depthFromRoot(root, path string) int {
	rel, err := filepath.Rel(root, path)
	if err != nil || rel == "." {
		return 0
	}
	return strings.Count(filepath.ToSlash(rel), "/") + 1
}

func exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
