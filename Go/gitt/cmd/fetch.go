package cmd

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"
	"strings"

	"gitt/internal/gitdiscovery"
	"gitt/internal/gitops"
	"gitt/internal/report"
)

func runFetch(args []string) error {
	fs := flag.NewFlagSet("fetch", flag.ContinueOnError)
	SetFlagSetOutput(fs, fmt.Sprintf("Usage: %s fetch [path] [flags]", appName))

	opts := ScanFlags{}
	RegisterScanFlags(fs, &opts, 4)

	if err := fs.Parse(args); err != nil {
		return err
	}
	if err := ValidateScanFlags("fetch", opts); err != nil {
		return err
	}

	positional := ""
	if fs.NArg() > 0 {
		positional = fs.Arg(0)
		if fs.NArg() > 1 {
			return fmt.Errorf("fetch: unexpected arguments after path: %q", fs.Args()[1])
		}
	}

	root, err := ResolveScanRoot(positional)
	if err != nil {
		return fmt.Errorf("fetch: %w", err)
	}

	ctx, stop := RootCommandContext()
	defer stop()

	repos, err := gitdiscovery.DiscoverRepos(gitdiscovery.DiscoverOptions{
		Root:          root,
		MaxDepth:      opts.MaxDepth,
		IncludeHidden: opts.IncludeHidden,
	})
	if err != nil {
		return fmt.Errorf("fetch: discovery failed: %w", err)
	}
	if len(repos) == 0 {
		fmt.Println("No git repositories found in current directory tree.")
		return nil
	}

	runner := gitops.ExecRunner{}
	results := RunIndexedParallel(ctx, repos, opts.Jobs, func(c context.Context, _ int, repo string) report.RepoResult {
		return fetchOneRepo(c, repo, opts, runner)
	})

	summary := report.Summary{}
	for _, result := range results {
		report.PrintResult(os.Stdout, result)
		summary.Add(result.Status)
	}
	report.PrintSummary(os.Stdout, summary, len(repos), report.SummaryModeFetch)

	if summary.Failed > 0 {
		return errPullFailed
	}
	return nil
}

func fetchOneRepo(ctx context.Context, repo string, opts ScanFlags, runner gitops.Runner) report.RepoResult {
	displayPath := ShortenRepoPath(repo)
	if opts.Verbose {
		Verbosef("Fetching %s\n", displayPath)
	}

	ok, err := gitops.IsRepo(ctx, runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if !ok {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "not a git work tree"}
	}

	stdout, stderr, err := gitops.FetchPrune(ctx, runner, repo)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: "interrupted"}
		}
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: CompactGitMessage(stderr, stdout)}
	}

	msg := CompactGitMessage(stdout, stderr)
	if msg == "" || msg == "ok" {
		msg = "fetch ok"
	}
	// Collapse long fetch output to first segment for table-style readability
	if strings.Contains(msg, "; ") && len(msg) > 120 {
		msg = msg[:120] + "..."
	}
	return report.RepoResult{Repo: displayPath, Status: report.StatusFetched, Message: msg}
}
