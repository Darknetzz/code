package main

import (
	"fmt"
	"io"
	"mime"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"regexp"
	"runtime"
	"strings"
	"time"
)

const version = "1.0.0"

var imageExts = map[string]struct{}{
	".jpg": {}, ".jpeg": {}, ".jfif": {}, ".png": {}, ".gif": {},
	".webp": {}, ".avif": {}, ".jxl": {}, ".bmp": {}, ".tif": {},
	".tiff": {}, ".heic": {}, ".heif": {}, ".ico": {}, ".svg": {},
	".jp2": {},
}

var mimeToExt = map[string]string{
	"image/jpeg":    ".jpg",
	"image/jpg":     ".jpg",
	"image/pjpeg":   ".jpg",
	"image/png":     ".png",
	"image/gif":     ".gif",
	"image/webp":    ".webp",
	"image/avif":    ".avif",
	"image/jxl":     ".jxl",
	"image/bmp":     ".bmp",
	"image/x-ms-bmp": ".bmp",
	"image/tiff":    ".tiff",
	"image/heic":    ".heic",
	"image/heif":    ".heif",
	"image/x-icon":  ".ico",
	"image/vnd.microsoft.icon": ".ico",
	"image/svg+xml": ".svg",
	"image/jp2":     ".jp2",
}

var contentDispositionFilename = regexp.MustCompile(`(?i)filename\*?=(?:UTF-8''|")?([^";\n]+)`)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) == 0 {
		printUsage()
		return 2
	}

	ytDlp := os.Getenv("DL_YT_DLP")
	if ytDlp == "" {
		ytDlp = "yt-dlp"
	}

	remaining := make([]string, 0, len(args))
	for i := 0; i < len(args); i++ {
		a := args[i]
		switch {
		case a == "--help" || a == "-h":
			// Alone or only with wrapper flags: show our help.
			// Otherwise leave for yt-dlp (handled after peel — see below).
			remaining = append(remaining, a)
		case a == "--version" || a == "-V":
			remaining = append(remaining, a)
		case a == "--yt-dlp":
			if i+1 >= len(args) {
				fmt.Fprintf(os.Stderr, "dl: --yt-dlp requires a path\n")
				return 2
			}
			ytDlp = args[i+1]
			i++
		case strings.HasPrefix(a, "--yt-dlp="):
			ytDlp = strings.TrimPrefix(a, "--yt-dlp=")
			if ytDlp == "" {
				fmt.Fprintf(os.Stderr, "dl: --yt-dlp requires a path\n")
				return 2
			}
		case a == "--dl-help":
			printUsage()
			return 0
		default:
			remaining = append(remaining, a)
		}
	}

	// Pure help/version with no URLs → document both modes (our help).
	if onlyHelpOrVersion(remaining) {
		if hasFlag(remaining, "--version") || hasFlag(remaining, "-V") {
			printVersion(ytDlp)
			return 0
		}
		printUsage()
		return 0
	}

	client := &http.Client{Timeout: 120 * time.Second}

	type urlSlot struct {
		argIndex int
		raw      string
		isImage  bool
	}

	var slots []urlSlot
	for i, a := range remaining {
		if isHTTPURL(a) {
			slots = append(slots, urlSlot{argIndex: i, raw: a})
		}
	}

	for i := range slots {
		slots[i].isImage = classifyImage(client, slots[i].raw)
	}

	var imageURLs []string
	imageIndex := map[int]struct{}{}
	for _, s := range slots {
		if s.isImage {
			imageURLs = append(imageURLs, s.raw)
			imageIndex[s.argIndex] = struct{}{}
		}
	}

	output := ""
	quiet := false
	ytArgs := make([]string, 0, len(remaining))

	allImages := len(imageURLs) > 0
	for _, s := range slots {
		if !s.isImage {
			allImages = false
			break
		}
	}

	if allImages {
		// Peel -o/--output and -q/--quiet only when every URL is an image
		// (so yt-dlp -o templates are never stolen).
		for i := 0; i < len(remaining); i++ {
			a := remaining[i]
			if _, skip := imageIndex[i]; skip {
				continue
			}
			switch {
			case a == "-o" || a == "--output":
				if i+1 >= len(remaining) {
					fmt.Fprintf(os.Stderr, "dl: %s requires a path\n", a)
					return 2
				}
				output = remaining[i+1]
				i++
			case strings.HasPrefix(a, "--output="):
				output = strings.TrimPrefix(a, "--output=")
			case strings.HasPrefix(a, "-o") && len(a) > 2 && !strings.HasPrefix(a, "--"):
				output = a[2:]
			case a == "-q" || a == "--quiet":
				quiet = true
			default:
				ytArgs = append(ytArgs, a)
			}
		}
	} else if len(imageURLs) > 0 {
		// Mixed: download images with default names; forward rest (incl. -o) to yt-dlp.
		for i, a := range remaining {
			if _, skip := imageIndex[i]; skip {
				continue
			}
			ytArgs = append(ytArgs, a)
		}
	} else {
		ytArgs = remaining
	}

	exitCode := 0

	if len(imageURLs) > 0 {
		if output != "" && len(imageURLs) > 1 {
			// -o as directory when multiple images
			info, err := os.Stat(output)
			if err != nil || !info.IsDir() {
				fmt.Fprintf(os.Stderr, "dl: with multiple image URLs, -o must be an existing directory\n")
				return 2
			}
		}
		for _, u := range imageURLs {
			pathOut, err := downloadImage(client, u, output, quiet)
			if err != nil {
				fmt.Fprintf(os.Stderr, "dl: %v\n", err)
				exitCode = 1
				continue
			}
			fmt.Println(pathOut)
		}
	}

	hasNonImageURL := false
	for _, s := range slots {
		if !s.isImage {
			hasNonImageURL = true
			break
		}
	}

	// Pure passthrough when nothing was an image; otherwise only if non-image URLs remain.
	if len(imageURLs) == 0 || hasNonImageURL {
		if len(ytArgs) == 0 {
			return exitCode
		}
		code := runYtDlp(ytDlp, ytArgs)
		if code != 0 {
			exitCode = code
		}
	}
	return exitCode
}

func printVersion(ytDlp string) {
	fmt.Printf("dl %s (yt-dlp wrapper + image download)\n", version)
	out, err := exec.Command(ytDlp, "--version").Output()
	if err != nil {
		fmt.Printf("yt-dlp: not found (%s)\n", ytDlp)
		return
	}
	fmt.Printf("yt-dlp %s\n", strings.TrimSpace(string(out)))
}

func onlyHelpOrVersion(args []string) bool {
	if len(args) == 0 {
		return true
	}
	for _, a := range args {
		switch a {
		case "-h", "--help", "-V", "--version":
			continue
		default:
			return false
		}
	}
	return true
}

func hasFlag(args []string, flag string) bool {
	for _, a := range args {
		if a == flag {
			return true
		}
	}
	return false
}

func isHTTPURL(s string) bool {
	u, err := url.Parse(s)
	if err != nil {
		return false
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return false
	}
	return u.Host != ""
}

func urlPathExt(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	return strings.ToLower(path.Ext(u.Path))
}

func hasImageExt(raw string) bool {
	_, ok := imageExts[urlPathExt(raw)]
	return ok
}

func mediaTypeIsImage(ct string) (string, bool) {
	if ct == "" {
		return "", false
	}
	media, _, err := mime.ParseMediaType(ct)
	if err != nil {
		media = strings.TrimSpace(strings.Split(ct, ";")[0])
	}
	media = strings.ToLower(media)
	if strings.HasPrefix(media, "image/") {
		return media, true
	}
	return "", false
}

func classifyImage(client *http.Client, raw string) bool {
	if hasImageExt(raw) {
		return true
	}
	// Extensionless (or non-image ext): probe Content-Type.
	req, err := http.NewRequest(http.MethodHead, raw, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "dl/"+version)
	resp, err := client.Do(req)
	if err != nil {
		return false
	}
	resp.Body.Close()
	if resp.StatusCode == http.StatusMethodNotAllowed || resp.StatusCode == http.StatusNotImplemented {
		// Some CDNs reject HEAD; try a ranged GET.
		return classifyImageViaGET(client, raw)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return false
	}
	_, ok := mediaTypeIsImage(resp.Header.Get("Content-Type"))
	return ok
}

func classifyImageViaGET(client *http.Client, raw string) bool {
	req, err := http.NewRequest(http.MethodGet, raw, nil)
	if err != nil {
		return false
	}
	req.Header.Set("User-Agent", "dl/"+version)
	req.Header.Set("Range", "bytes=0-0")
	resp, err := client.Do(req)
	if err != nil {
		return false
	}
	io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 400 {
		return false
	}
	_, ok := mediaTypeIsImage(resp.Header.Get("Content-Type"))
	return ok
}

func downloadImage(client *http.Client, raw, output string, quiet bool) (string, error) {
	req, err := http.NewRequest(http.MethodGet, raw, nil)
	if err != nil {
		return "", err
	}
	req.Header.Set("User-Agent", "dl/"+version)
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("%s: %w", raw, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", fmt.Errorf("%s: %s", raw, resp.Status)
	}

	ct := resp.Header.Get("Content-Type")
	media, isImg := mediaTypeIsImage(ct)
	if !isImg && !hasImageExt(raw) {
		return "", fmt.Errorf("%s: not an image (Content-Type %q)", raw, ct)
	}

	name := filenameFromDisposition(resp.Header.Get("Content-Disposition"))
	if name == "" {
		name = basenameFromURL(raw)
	}
	if name == "" || name == "/" || name == "." {
		name = "image"
	}
	name = sanitizeFilename(name)

	ext := strings.ToLower(filepath.Ext(name))
	if _, ok := imageExts[ext]; !ok {
		if e, ok := mimeToExt[media]; ok {
			name += e
		} else if hasImageExt(raw) {
			name += urlPathExt(raw)
		} else if media != "" {
			// image/foo → .foo
			if parts := strings.SplitN(media, "/", 2); len(parts) == 2 && parts[1] != "" {
				sub := parts[1]
				if i := strings.IndexAny(sub, "+;"); i >= 0 {
					sub = sub[:i]
				}
				name += "." + sub
			} else {
				name += ".img"
			}
		} else {
			name += ".img"
		}
	}

	destPath, err := resolveOutputPath(output, name)
	if err != nil {
		return "", err
	}

	if !quiet {
		fmt.Fprintf(os.Stderr, "dl: downloading %s → %s\n", raw, destPath)
	}

	f, err := os.Create(destPath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	if _, err := io.Copy(f, resp.Body); err != nil {
		os.Remove(destPath)
		return "", err
	}
	return destPath, nil
}

func filenameFromDisposition(h string) string {
	if h == "" {
		return ""
	}
	if m := contentDispositionFilename.FindStringSubmatch(h); len(m) == 2 {
		name, err := url.QueryUnescape(strings.Trim(m[1], `"`))
		if err != nil {
			return sanitizeFilename(strings.Trim(m[1], `"`))
		}
		return filepath.Base(name)
	}
	_, params, err := mime.ParseMediaType(h)
	if err == nil {
		if fn, ok := params["filename"]; ok {
			return filepath.Base(fn)
		}
	}
	return ""
}

func basenameFromURL(raw string) string {
	u, err := url.Parse(raw)
	if err != nil {
		return ""
	}
	base := path.Base(u.Path)
	if base == "." || base == "/" {
		return ""
	}
	return base
}

func sanitizeFilename(name string) string {
	name = filepath.Base(name)
	replacer := strings.NewReplacer(
		`<`, "_", `>`, "_", `:`, "_", `"`, "_",
		`/`, "_", `\`, "_", `|`, "_", `?`, "_", `*`, "_",
	)
	name = replacer.Replace(name)
	name = strings.TrimSpace(name)
	if name == "" || name == "." || name == ".." {
		return "image"
	}
	return name
}

func resolveOutputPath(output, name string) (string, error) {
	if output == "" {
		return filepath.Clean(name), nil
	}
	info, err := os.Stat(output)
	if err == nil && info.IsDir() {
		return filepath.Join(output, name), nil
	}
	if strings.HasSuffix(output, string(os.PathSeparator)) || strings.HasSuffix(output, "/") || strings.HasSuffix(output, "\\") {
		if err := os.MkdirAll(output, 0o755); err != nil {
			return "", err
		}
		return filepath.Join(output, name), nil
	}
	// Treat as file path; ensure parent exists.
	dir := filepath.Dir(output)
	if dir != "" && dir != "." {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return "", err
		}
	}
	return output, nil
}

func runYtDlp(bin string, args []string) int {
	if runtime.GOOS != "windows" {
		path, err := exec.LookPath(bin)
		if err == nil {
			argv := append([]string{path}, args...)
			if err := syscallExec(path, argv, os.Environ()); err != nil {
				fmt.Fprintf(os.Stderr, "dl: exec %s: %v\n", bin, err)
				// fall through to Command
			}
		}
	}

	cmd := exec.Command(bin, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	err := cmd.Run()
	if err == nil {
		return 0
	}
	if ee, ok := err.(*exec.ExitError); ok {
		return ee.ExitCode()
	}
	fmt.Fprintf(os.Stderr, "dl: %s: %v\n", bin, err)
	return 1
}

func printUsage() {
	fmt.Fprintf(os.Stderr, `dl %s — download images over HTTP, or forward to yt-dlp

Usage:
  dl [options] <url> [url...]
  dl [yt-dlp-options] <url>   # non-image URLs pass through to yt-dlp

Image URLs (path ends with an image extension, or Content-Type is image/*)
are downloaded with HTTP. Everything else is forwarded unchanged to yt-dlp.

Wrapper options (not passed to yt-dlp):
  --yt-dlp PATH   yt-dlp binary (default: yt-dlp, or env DL_YT_DLP)
  --dl-help       Show this help

When downloading images, these are also consumed by dl (not forwarded):
  -o, --output PATH   Output file (single URL) or directory
  -q, --quiet         Suppress progress on stderr (saved path still on stdout)

Supported image extensions:
  jpg jpeg jfif png gif webp avif jxl bmp tif tiff heic heif ico svg jp2

Install (replace existing dl → yt-dlp symlink):
  go build -o dl.exe .
  # put dl.exe on PATH where the old symlink lived

Examples:
  dl https://example.com/photo.avif
  dl -o out.webp https://cdn.example/img   # extensionless if Content-Type is image/*
  dl -f bv+ba https://www.youtube.com/watch?v=dQw4w9WgXcQ
`, version)
}
