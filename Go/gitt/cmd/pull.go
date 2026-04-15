package cmd

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"gitt/internal/gitdiscovery"
	"gitt/internal/gitops"
	"gitt/internal/report"
)

type pullOptions struct {
	dryRun        bool
	maxDepth      int
	jobs          int
	includeHidden bool
	verbose       bool
}

func runPull(args []string) error {
	fs := flag.NewFlagSet("pull", flag.ContinueOnError)
	fs.SetOutput(os.Stderr)

	opts := pullOptions{}
	fs.BoolVar(&opts.dryRun, "dry-run", false, "show repositories without running git pull")
	fs.IntVar(&opts.maxDepth, "max-depth", -1, "max directory depth to scan (-1 for unlimited)")
	fs.IntVar(&opts.jobs, "jobs", 4, "number of repositories processed in parallel")
	fs.BoolVar(&opts.includeHidden, "include-hidden", false, "include hidden directories while scanning")
	fs.BoolVar(&opts.verbose, "verbose", false, "print extra details while running")
	fs.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s pull [flags]\n\n", appName)
		fs.PrintDefaults()
	}

	if err := fs.Parse(args); err != nil {
		return err
	}
	if opts.jobs < 1 {
		return fmt.Errorf("pull: --jobs must be >= 1")
	}

	root, err := os.Getwd()
	if err != nil {
		return fmt.Errorf("pull: could not resolve current directory: %w", err)
	}

	repos, err := gitdiscovery.DiscoverRepos(gitdiscovery.DiscoverOptions{
		Root:          root,
		MaxDepth:      opts.maxDepth,
		IncludeHidden: opts.includeHidden,
	})
	if err != nil {
		return fmt.Errorf("pull: discovery failed: %w", err)
	}
	if len(repos) == 0 {
		fmt.Println("No git repositories found in current directory tree.")
		return nil
	}

	runner := gitops.ExecRunner{}
	results := runPullWorkers(repos, opts, runner)

	summary := report.Summary{}
	for _, result := range results {
		report.PrintResult(os.Stdout, result)
		summary.Add(result.Status)
	}
	report.PrintSummary(os.Stdout, summary, len(repos))

	if summary.Failed > 0 {
		return errPullFailed
	}
	return nil
}

func runPullWorkers(repos []string, opts pullOptions, runner gitops.Runner) []report.RepoResult {
	type job struct {
		idx  int
		repo string
	}
	type jobResult struct {
		idx    int
		result report.RepoResult
	}

	jobs := make(chan job)
	results := make(chan jobResult, len(repos))
	workers := opts.jobs
	if workers > len(repos) {
		workers = len(repos)
	}

	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				results <- jobResult{
					idx:    j.idx,
					result: pullOneRepo(j.repo, opts, runner),
				}
			}
		}()
	}

	for i, repo := range repos {
		jobs <- job{idx: i, repo: repo}
	}
	close(jobs)

	wg.Wait()
	close(results)

	ordered := make([]report.RepoResult, len(repos))
	for item := range results {
		ordered[item.idx] = item.result
	}
	return ordered
}

func pullOneRepo(repo string, opts pullOptions, runner gitops.Runner) report.RepoResult {
	displayPath := shortenRepoPath(repo)
	if opts.verbose {
		fmt.Fprintf(os.Stderr, "Inspecting %s\n", displayPath)
	}

	ok, err := gitops.IsRepo(runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if !ok {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "not a git work tree"}
	}

	dirty, err := gitops.IsDirty(runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if dirty {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "working tree is dirty"}
	}

	if opts.dryRun {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "dry-run"}
	}

	stdout, stderr, err := gitops.PullFFOnly(runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: compactGitMessage(stderr, stdout)}
	}

	msg := compactGitMessage(stdout, stderr)
	if isUpToDate(stdout, stderr) {
		return report.RepoResult{Repo: displayPath, Status: report.StatusUpToDate, Message: msg}
	}
	return report.RepoResult{Repo: displayPath, Status: report.StatusUpdated, Message: msg}
}

func isUpToDate(stdout, stderr string) bool {
	combined := strings.ToLower(stdout + "\n" + stderr)
	return strings.Contains(combined, "already up to date") ||
		strings.Contains(combined, "already up-to-date")
}

func compactGitMessage(primary, fallback string) string {
	msg := strings.TrimSpace(primary)
	if msg == "" {
		msg = strings.TrimSpace(fallback)
	}
	if msg == "" {
		return "ok"
	}
	msg = strings.ReplaceAll(msg, "\r\n", "; ")
	msg = strings.ReplaceAll(msg, "\n", "; ")
	return msg
}

func shortenRepoPath(absPath string) string {
	cwd, err := os.Getwd()
	if err != nil {
		return absPath
	}
	rel, err := filepath.Rel(cwd, absPath)
	if err != nil || rel == "." {
		return "."
	}
	return filepath.ToSlash(rel)
}
