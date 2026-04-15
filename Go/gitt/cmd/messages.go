package cmd

import "strings"

// CompactGitMessage picks a single-line summary from git stdout/stderr.
func CompactGitMessage(primary, fallback string) string {
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
