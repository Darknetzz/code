package cmd

import (
	"context"
	"errors"
	"flag"
	"fmt"
	"os"

	"gitt/internal/gitdiscovery"
	"gitt/internal/gitops"
	"gitt/internal/report"
)

type pullOptions struct {
	ScanFlags
	dryRun bool
}

func runPull(args []string) error {
	fs := flag.NewFlagSet("pull", flag.ContinueOnError)
	SetFlagSetOutput(fs, fmt.Sprintf("Usage: %s pull [path] [flags]", appName))

	opts := pullOptions{}
	RegisterScanFlags(fs, &opts.ScanFlags, 4)
	fs.BoolVar(&opts.dryRun, "dry-run", false, "show repositories without running git pull")

	if err := fs.Parse(args); err != nil {
		return err
	}
	if err := ValidateScanFlags("pull", opts.ScanFlags); err != nil {
		return err
	}

	positional := ""
	if fs.NArg() > 0 {
		positional = fs.Arg(0)
		if fs.NArg() > 1 {
			return fmt.Errorf("pull: unexpected arguments after path: %q", fs.Args()[1])
		}
	}

	root, err := ResolveScanRoot(positional)
	if err != nil {
		return fmt.Errorf("pull: %w", err)
	}

	ctx, stop := RootCommandContext()
	defer stop()

	repos, err := gitdiscovery.DiscoverRepos(gitdiscovery.DiscoverOptions{
		Root:          root,
		MaxDepth:      opts.MaxDepth,
		IncludeHidden: opts.IncludeHidden,
	})
	if err != nil {
		return fmt.Errorf("pull: discovery failed: %w", err)
	}
	if len(repos) == 0 {
		fmt.Println("No git repositories found in current directory tree.")
		return nil
	}

	runner := gitops.ExecRunner{}
	results := RunIndexedParallel(ctx, repos, opts.Jobs, func(c context.Context, _ int, repo string) report.RepoResult {
		return pullOneRepo(c, repo, opts, runner)
	})

	summary := report.Summary{}
	for _, result := range results {
		report.PrintResult(os.Stdout, result)
		summary.Add(result.Status)
	}
	report.PrintSummary(os.Stdout, summary, len(repos), report.SummaryModePull)

	if summary.Failed > 0 {
		return errPullFailed
	}
	return nil
}

func pullOneRepo(ctx context.Context, repo string, opts pullOptions, runner gitops.Runner) report.RepoResult {
	displayPath := ShortenRepoPath(repo)
	if opts.Verbose {
		Verbosef("Inspecting %s\n", displayPath)
	}

	ok, err := gitops.IsRepo(ctx, runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if !ok {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "not a git work tree"}
	}

	dirty, err := gitops.IsDirty(ctx, runner, repo)
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}
	if dirty {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "working tree is dirty"}
	}

	if opts.dryRun {
		return report.RepoResult{Repo: displayPath, Status: report.StatusSkipped, Message: "dry-run"}
	}

	before, err := gitops.RevParse(ctx, runner, repo, "HEAD")
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}

	stdout, stderr, err := gitops.PullFFOnly(ctx, runner, repo)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: "interrupted"}
		}
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: CompactGitMessage(stderr, stdout)}
	}

	after, err := gitops.RevParse(ctx, runner, repo, "HEAD")
	if err != nil {
		return report.RepoResult{Repo: displayPath, Status: report.StatusFailed, Message: err.Error()}
	}

	msg := CompactGitMessage(stdout, stderr)
	if before == after {
		return report.RepoResult{Repo: displayPath, Status: report.StatusUpToDate, Message: msg}
	}
	return report.RepoResult{Repo: displayPath, Status: report.StatusUpdated, Message: msg}
}
