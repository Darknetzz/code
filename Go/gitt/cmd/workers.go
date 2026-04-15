package cmd

import (
	"context"
	"sync"

	"gitt/internal/report"
)

// RunIndexedParallel runs fn for each repo with up to jobs workers, preserving result order by index.
func RunIndexedParallel(
	ctx context.Context,
	repos []string,
	jobs int,
	fn func(ctx context.Context, idx int, repo string) report.RepoResult,
) []report.RepoResult {
	type job struct {
		idx  int
		repo string
	}
	type jobResult struct {
		idx    int
		result report.RepoResult
	}

	if len(repos) == 0 {
		return nil
	}

	if jobs < 1 {
		jobs = 1
	}
	workers := jobs
	if workers > len(repos) {
		workers = len(repos)
	}

	jobCh := make(chan job)
	results := make(chan jobResult, len(repos))

	var wg sync.WaitGroup
	for range workers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobCh {
				results <- jobResult{idx: j.idx, result: fn(ctx, j.idx, j.repo)}
			}
		}()
	}

	for i, repo := range repos {
		jobCh <- job{idx: i, repo: repo}
	}
	close(jobCh)

	wg.Wait()
	close(results)

	ordered := make([]report.RepoResult, len(repos))
	for item := range results {
		ordered[item.idx] = item.result
	}
	return ordered
}
