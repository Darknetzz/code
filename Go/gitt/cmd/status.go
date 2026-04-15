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

func runStatus(args []string) error {
	fs := flag.NewFlagSet("status", flag.ContinueOnError)
	SetFlagSetOutput(fs, fmt.Sprintf("Usage: %s status [path] [flags]", appName))

	opts := ScanFlags{}
	RegisterScanFlags(fs, &opts, 4)

	if err := fs.Parse(args); err != nil {
		return err
	}
	if err := ValidateScanFlags("status", opts); err != nil {
		return err
	}

	positional := ""
	if fs.NArg() > 0 {
		positional = fs.Arg(0)
		if fs.NArg() > 1 {
			return fmt.Errorf("status: unexpected arguments after path: %q", fs.Args()[1])
		}
	}

	root, err := ResolveScanRoot(positional)
	if err != nil {
		return fmt.Errorf("status: %w", err)
	}

	ctx, stop := RootCommandContext()
	defer stop()

	repos, err := gitdiscovery.DiscoverRepos(gitdiscovery.DiscoverOptions{
		Root:          root,
		MaxDepth:      opts.MaxDepth,
		IncludeHidden: opts.IncludeHidden,
	})
	if err != nil {
		return fmt.Errorf("status: discovery failed: %w", err)
	}
	if len(repos) == 0 {
		fmt.Println("No git repositories found in current directory tree.")
		return nil
	}

	runner := gitops.ExecRunner{}
	results := RunIndexedParallel(ctx, repos, opts.Jobs, func(c context.Context, _ int, repo string) report.RepoResult {
		return statusOneRepo(c, repo, opts, runner)
	})

	summary := report.Summary{}
	for _, result := range results {
		report.PrintResult(os.Stdout, result)
		summary.Add(result.Status)
	}
	report.PrintSummary(os.Stdout, summary, len(repos), report.SummaryModeStatus)

	if summary.Failed > 0 {
		return errPullFailed
	}
	return nil
}

func statusOneRepo(ctx context.Context, repo string, opts ScanFlags, runner gitops.Runner) report.RepoResult {
	displayPath := ShortenRepoPath(repo)
	if opts.Verbose {
		Verbosef("Status %s\n", displayPath)
	}

	ok, err := gitops.IsRepo(ctx, runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if !ok {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "not a git work tree"}
	}

	out, err := gitops.StatusPorcelain(ctx, runner, repo)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: "interrupted"}
		}
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}

	trimmed := strings.TrimSpace(out)
	if trimmed == "" {
		return report.RepoResult{Repo: displayPath, Status: report.StatusClean, Message: "clean"}
	}

	lines := strings.Split(trimmed, "\n")
	msg := fmt.Sprintf("%d changed path(s)", len(lines))
	if len(lines) == 1 {
		msg = strings.TrimSpace(lines[0])
	}
	return report.RepoResult{Repo: displayPath, Status: report.StatusDirty, Message: msg}
}
