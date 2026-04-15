package version

import "fmt"

var (
	// Version is the semantic version set at build time.
	Version = "dev"
	// Commit is the git commit hash set at build time.
	Commit = "none"
	// BuildDate is the build timestamp set at build time.
	BuildDate = "unknown"
)

func String() string {
	return fmt.Sprintf("%s (commit=%s, built=%s)", Version, Commit, BuildDate)
}
