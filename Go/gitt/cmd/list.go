package cmd

import (
	"flag"
	"fmt"
	"os"

	"gitt/internal/gitdiscovery"
)

func runList(args []string) error {
	fs := flag.NewFlagSet("list", flag.ContinueOnError)
	SetFlagSetOutput(fs, fmt.Sprintf("Usage: %s list [path] [flags]", appName))

	var maxDepth int
	var includeHidden bool
	fs.IntVar(&maxDepth, "max-depth", -1, "max directory depth to scan (-1 for unlimited)")
	fs.BoolVar(&includeHidden, "include-hidden", false, "include hidden directories while scanning")

	if err := fs.Parse(args); err != nil {
		return err
	}

	positional := ""
	if fs.NArg() > 0 {
		positional = fs.Arg(0)
		if fs.NArg() > 1 {
			return fmt.Errorf("list: unexpected arguments after path: %q", fs.Args()[1])
		}
	}

	root, err := ResolveScanRoot(positional)
	if err != nil {
		return fmt.Errorf("list: %w", err)
	}

	repos, err := gitdiscovery.DiscoverRepos(gitdiscovery.DiscoverOptions{
		Root:          root,
		MaxDepth:      maxDepth,
		IncludeHidden: includeHidden,
	})
	if err != nil {
		return fmt.Errorf("list: discovery failed: %w", err)
	}

	for _, repo := range repos {
		fmt.Println(ShortenRepoPath(repo))
	}
	if len(repos) == 0 {
		fmt.Println("No git repositories found.")
	} else {
		fmt.Fprintf(os.Stderr, "\nTotal: %d\n", len(repos))
	}
	return nil
}
