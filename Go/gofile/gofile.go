// gofile — CLI to inspect and manage files
//
// Usage:
//
//	gofile info [options] <path>...
//	gofile hash [options] <path>...
//	gofile type <path>...
//	gofile size [options] <path>...
//	gofile list [options] [dir]
//	gofile cat [path]...
//	gofile head [options] [path]...
//	gofile tail [options] [path]...
//	gofile realpath <path>
//	gofile copy [options] <src> <dst>
//	gofile move <src> <dst>
//	gofile remove [options] <path>...
//	gofile mkdir [options] <path>...
//	gofile touch <path>...
package main

import (
	"bufio"
	"crypto/md5"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/hex"
	"flag"
	"fmt"
	"hash"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

var progName string

func main() {
	progName = filepath.Base(os.Args[0])
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(0)
	}
	cmd := strings.ToLower(os.Args[1])
	args := os.Args[2:]

	var exitCode int
	switch cmd {
	case "info", "stat":
		exitCode = runInfo(args)
	case "hash":
		exitCode = runHash(args)
	case "type", "mime":
		exitCode = runType(args)
	case "size":
		exitCode = runSize(args)
	case "list", "ls":
		exitCode = runList(args)
	case "cat":
		exitCode = runCat(args)
	case "head":
		exitCode = runHead(args)
	case "tail":
		exitCode = runTail(args)
	case "realpath", "real":
		exitCode = runRealpath(args)
	case "copy", "cp":
		exitCode = runCopy(args)
	case "move", "mv":
		exitCode = runMove(args)
	case "remove", "rm":
		exitCode = runRemove(args)
	case "mkdir":
		exitCode = runMkdir(args)
	case "touch":
		exitCode = runTouch(args)
	case "help", "-h", "--help":
		if len(args) > 0 {
			printCommandHelp(args[0])
		} else {
			printUsage()
		}
		os.Exit(0)
	default:
		fmt.Fprintf(os.Stderr, "%s: unknown command %q\n", progName, cmd)
		printUsage()
		os.Exit(1)
	}
	os.Exit(exitCode)
}

func printUsage() {
	fmt.Fprintf(os.Stderr, "%s — inspect and manage files\n\n", progName)
	fmt.Fprintf(os.Stderr, "Usage:\n  %s <command> [options] [args]\n\n", progName)
	fmt.Fprintf(os.Stderr, "Inspect:\n")
	fmt.Fprintf(os.Stderr, "  info         File/dir metadata (size, mode, mtime)\n")
	fmt.Fprintf(os.Stderr, "  hash         Compute checksum (md5, sha256, sha512)\n")
	fmt.Fprintf(os.Stderr, "  type         MIME type / file type\n")
	fmt.Fprintf(os.Stderr, "  size         Human-readable size (optional -R for dirs)\n")
	fmt.Fprintf(os.Stderr, "  list         List directory (ls-style)\n")
	fmt.Fprintf(os.Stderr, "  cat          Print file contents\n")
	fmt.Fprintf(os.Stderr, "  head         First N lines or bytes\n")
	fmt.Fprintf(os.Stderr, "  tail         Last N lines or bytes\n")
	fmt.Fprintf(os.Stderr, "  realpath     Resolve to absolute path\n")
	fmt.Fprintf(os.Stderr, "\nManage:\n")
	fmt.Fprintf(os.Stderr, "  copy         Copy file(s) to destination\n")
	fmt.Fprintf(os.Stderr, "  move         Move file(s)\n")
	fmt.Fprintf(os.Stderr, "  remove       Delete file(s) (-r for recursive)\n")
	fmt.Fprintf(os.Stderr, "  mkdir        Create directory (-p for parents)\n")
	fmt.Fprintf(os.Stderr, "  touch        Update mtime or create empty file\n")
	fmt.Fprintf(os.Stderr, "\n  %s help <command>\n", progName)
}

func printCommandHelp(cmd string) {
	switch strings.ToLower(cmd) {
	case "info", "stat":
		printInfoUsage()
	case "hash":
		printHashUsage()
	case "type", "mime":
		printTypeUsage()
	case "size":
		printSizeUsage()
	case "list", "ls":
		printListUsage()
	case "cat":
		printCatUsage()
	case "head":
		printHeadUsage()
	case "tail":
		printTailUsage()
	case "realpath", "real":
		printRealpathUsage()
	case "copy", "cp":
		printCopyUsage()
	case "move", "mv":
		printMoveUsage()
	case "remove", "rm":
		printRemoveUsage()
	case "mkdir":
		printMkdirUsage()
	case "touch":
		printTouchUsage()
	default:
		fmt.Fprintf(os.Stderr, "%s: unknown command %q\n", progName, cmd)
	}
}

// ---- shared helpers ----

func formatSize(n int64) string {
	const unit = 1024
	if n < unit {
		return fmt.Sprintf("%d B", n)
	}
	div, exp := int64(unit), 0
	for v := n / unit; v >= unit; v /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.1f %cB", float64(n)/float64(div), "KMGTPE"[exp])
}

func newHasher(algo string) (hash.Hash, error) {
	switch strings.ToLower(algo) {
	case "md5":
		return md5.New(), nil
	case "sha256":
		return sha256.New(), nil
	case "sha512":
		return sha512.New(), nil
	default:
		return nil, fmt.Errorf("unsupported algorithm %q (use md5, sha256, sha512)", algo)
	}
}

func hashReader(r io.Reader, algo string) (string, error) {
	h, err := newHasher(algo)
	if err != nil {
		return "", err
	}
	if _, err := io.Copy(h, r); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// ---- info ----

func printInfoUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s info [-l] <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  -l  Long format (one line per field)\n")
}

func runInfo(args []string) int {
	fs := flag.NewFlagSet("info", flag.ExitOnError)
	long := fs.Bool("l", false, "Long format")
	fs.Usage = func() { printInfoUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) == 0 {
		printInfoUsage()
		return 1
	}
	ok := true
	for _, p := range paths {
		if err := printFileInfo(p, *long); err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

func printFileInfo(path string, long bool) error {
	path, err := filepath.Abs(path)
	if err != nil {
		return err
	}
	info, err := os.Stat(path)
	if err != nil {
		return err
	}
	mode := info.Mode()
	kind := "file"
	if mode.IsDir() {
		kind = "dir"
	} else if mode&os.ModeSymlink != 0 {
		kind = "symlink"
	}
	if long {
		fmt.Printf("path:   %s\n", path)
		fmt.Printf("size:   %d (%s)\n", info.Size(), formatSize(info.Size()))
		fmt.Printf("mode:   %s\n", mode.String())
		fmt.Printf("mtime:  %s\n", info.ModTime().Format(time.RFC3339))
		fmt.Printf("type:   %s\n", kind)
	} else {
		fmt.Printf("%s  %s  %s  %s\n", path, formatSize(info.Size()), mode.String(), info.ModTime().Format("2006-01-02 15:04:05"))
	}
	return nil
}

// ---- hash ----

func printHashUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s hash [-a algo] [-q] <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  -a  md5, sha256, sha512 (default sha256)\n")
	fmt.Fprintf(os.Stderr, "  -q  Print only hash\n")
}

func runHash(args []string) int {
	fs := flag.NewFlagSet("hash", flag.ExitOnError)
	algo := fs.String("a", "sha256", "Algorithm")
	quiet := fs.Bool("q", false, "Quiet")
	fs.Usage = func() { printHashUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) == 0 {
		// stdin
		sum, err := hashReader(os.Stdin, *algo)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			return 1
		}
		if *quiet {
			fmt.Println(sum)
		} else {
			fmt.Printf("%s  -\n", sum)
		}
		return 0
	}
	ok := true
	for _, p := range paths {
		f, err := os.Open(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		sum, err := hashReader(f, *algo)
		f.Close()
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		if *quiet {
			fmt.Println(sum)
		} else {
			fmt.Printf("%s  %s\n", sum, p)
		}
	}
	if !ok {
		return 1
	}
	return 0
}

// ---- type (MIME) ----

func printTypeUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s type <path>...\n", progName)
}

func runType(args []string) int {
	if len(args) == 0 {
		printTypeUsage()
		return 1
	}
	ok := true
	for _, p := range args {
		mime, err := detectMIME(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		fmt.Printf("%s: %s\n", p, mime)
	}
	if !ok {
		return 1
	}
	return 0
}

func detectMIME(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	info, err := f.Stat()
	if err != nil {
		return "", err
	}
	if info.IsDir() {
		return "inode/directory", nil
	}
	buf := make([]byte, 512)
	n, _ := f.Read(buf)
	buf = buf[:n]
	return http.DetectContentType(buf), nil
}

// ---- size ----

func printSizeUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s size [-R] <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  -R  Recursive (total for dirs)\n")
}

func runSize(args []string) int {
	fs := flag.NewFlagSet("size", flag.ExitOnError)
	recursive := fs.Bool("R", false, "Recursive")
	fs.Usage = func() { printSizeUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) == 0 {
		printSizeUsage()
		return 1
	}
	ok := true
	for _, p := range paths {
		var n int64
		var err error
		if *recursive {
			n, err = dirSize(p)
		} else {
			n, err = fileSize(p)
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		fmt.Printf("%s  %s\n", formatSize(n), p)
	}
	if !ok {
		return 1
	}
	return 0
}

func fileSize(path string) (int64, error) {
	info, err := os.Stat(path)
	if err != nil {
		return 0, err
	}
	return info.Size(), nil
}

func dirSize(path string) (int64, error) {
	var total int64
	err := filepath.Walk(path, func(_ string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		if !info.IsDir() {
			total += info.Size()
		}
		return nil
	})
	return total, err
}

// ---- list ----

func printListUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s list [-l] [-R] [dir]\n", progName)
	fmt.Fprintf(os.Stderr, "  -l  Long format (mode, size, mtime, name)\n")
	fmt.Fprintf(os.Stderr, "  -R  Recursive\n")
}

func runList(args []string) int {
	fs := flag.NewFlagSet("list", flag.ExitOnError)
	long := fs.Bool("l", false, "Long")
	recursive := fs.Bool("R", false, "Recursive")
	fs.Usage = func() { printListUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	dir := "."
	if len(fs.Args()) > 0 {
		dir = fs.Arg(0)
	}
	if *recursive {
		return listRecursive(dir, *long)
	}
	return listDir(dir, *long)
}

func listDir(dir string, long bool) int {
	entries, err := os.ReadDir(dir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		return 1
	}
	for _, e := range entries {
		info, err := e.Info()
		if err != nil {
			continue
		}
		if long {
			fmt.Printf("%s  %8s  %s  %s\n", info.Mode().String(), formatSize(info.Size()), info.ModTime().Format("2006-01-02 15:04"), e.Name())
		} else {
			fmt.Println(e.Name())
		}
	}
	return 0
}

func listRecursive(dir string, long bool) int {
	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			return nil
		}
		rel, _ := filepath.Rel(dir, path)
		if rel == "." {
			return nil
		}
		if long {
			fmt.Printf("%s  %8s  %s  %s\n", info.Mode().String(), formatSize(info.Size()), info.ModTime().Format("2006-01-02 15:04"), path)
		} else {
			fmt.Println(path)
		}
		return nil
	})
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		return 1
	}
	return 0
}

// ---- cat ----

func printCatUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s cat [path]...\n", progName)
	fmt.Fprintf(os.Stderr, "  With no path, reads stdin.\n")
}

func runCat(args []string) int {
	if len(args) == 0 {
		_, err := io.Copy(os.Stdout, os.Stdin)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			return 1
		}
		return 0
	}
	ok := true
	for _, p := range args {
		f, err := os.Open(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		_, err = io.Copy(os.Stdout, f)
		f.Close()
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

// ---- head / tail (shared parsing) ----

func parseHeadTailArgs(args []string) (n int, bytes bool, paths []string) {
	n = 10
	bytes = false
	for len(args) > 0 && strings.HasPrefix(args[0], "-") {
		switch args[0] {
		case "-n":
			if len(args) < 2 {
				return 0, false, nil
			}
			fmt.Sscanf(args[1], "%d", &n)
			args = args[2:]
		case "-c":
			if len(args) < 2 {
				return 0, false, nil
			}
			fmt.Sscanf(args[1], "%d", &n)
			bytes = true
			args = args[2:]
		default:
			if strings.HasPrefix(args[0], "-n") {
				fmt.Sscanf(args[0][2:], "%d", &n)
			} else if strings.HasPrefix(args[0], "-c") {
				fmt.Sscanf(args[0][2:], "%d", &n)
				bytes = true
			}
			args = args[1:]
		}
	}
	return n, bytes, args
}

func printHeadUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s head [-n N] [-c N] [path]...\n", progName)
	fmt.Fprintf(os.Stderr, "  -n N  First N lines (default 10)\n")
	fmt.Fprintf(os.Stderr, "  -c N  First N bytes\n")
}

func runHead(args []string) int {
	n, byBytes, paths := parseHeadTailArgs(args)
	if paths == nil && len(args) > 0 {
		printHeadUsage()
		return 1
	}
	if len(paths) == 0 {
		return headReader(os.Stdin, n, byBytes, "-")
	}
	ok := true
	for i, p := range paths {
		f, err := os.Open(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		if len(paths) > 1 {
			if i > 0 {
				fmt.Println()
			}
			fmt.Printf("==> %s <==\n", p)
		}
		headReader(f, n, byBytes, p)
		f.Close()
	}
	if !ok {
		return 1
	}
	return 0
}

func headReader(r io.Reader, n int, byBytes bool, name string) int {
	if byBytes {
		buf := make([]byte, n)
		read, err := io.ReadFull(r, buf)
		if read > 0 {
			os.Stdout.Write(buf[:read])
		}
		if err != nil && err != io.EOF && err != io.ErrUnexpectedEOF {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			return 1
		}
		return 0
	}
	sc := bufio.NewScanner(r)
	for i := 0; i < n && sc.Scan(); i++ {
		fmt.Println(sc.Text())
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		return 1
	}
	return 0
}

func printTailUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s tail [-n N] [-c N] [path]...\n", progName)
	fmt.Fprintf(os.Stderr, "  -n N  Last N lines (default 10)\n")
	fmt.Fprintf(os.Stderr, "  -c N  Last N bytes\n")
}

func runTail(args []string) int {
	n, byBytes, paths := parseHeadTailArgs(args)
	if paths == nil && len(args) > 0 {
		printTailUsage()
		return 1
	}
	if len(paths) == 0 {
		return tailReader(os.Stdin, n, byBytes, "-")
	}
	ok := true
	for i, p := range paths {
		f, err := os.Open(p)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		if len(paths) > 1 {
			if i > 0 {
				fmt.Println()
			}
			fmt.Printf("==> %s <==\n", p)
		}
		tailReader(f, n, byBytes, p)
		f.Close()
	}
	if !ok {
		return 1
	}
	return 0
}

func tailReader(r io.Reader, n int, byBytes bool, name string) int {
	if byBytes {
		buf, err := io.ReadAll(r)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			return 1
		}
		start := len(buf) - n
		if start < 0 {
			start = 0
		}
		os.Stdout.Write(buf[start:])
		return 0
	}
	lines := make([]string, 0, n+1)
	sc := bufio.NewScanner(r)
	for sc.Scan() {
		lines = append(lines, sc.Text())
		if len(lines) > n {
			lines = lines[1:]
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		return 1
	}
	for _, line := range lines {
		fmt.Println(line)
	}
	return 0
}

// ---- realpath ----

func printRealpathUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s realpath <path>\n", progName)
}

func runRealpath(args []string) int {
	if len(args) != 1 {
		printRealpathUsage()
		return 1
	}
	abs, err := filepath.Abs(args[0])
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		return 1
	}
	// resolve symlinks if possible
	resolved, err := filepath.EvalSymlinks(abs)
	if err == nil {
		abs = resolved
	}
	fmt.Println(abs)
	return 0
}

// ---- copy ----

func printCopyUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s copy [-r] <src> [src...] <dst>\n", progName)
	fmt.Fprintf(os.Stderr, "  -r  Recursive (for dirs)\n")
}

func runCopy(args []string) int {
	fs := flag.NewFlagSet("copy", flag.ExitOnError)
	recursive := fs.Bool("r", false, "Recursive")
	fs.Usage = func() { printCopyUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) < 2 {
		printCopyUsage()
		return 1
	}
	dst := paths[len(paths)-1]
	srcs := paths[:len(paths)-1]
	ok := true
	for _, src := range srcs {
		if err := copyPath(src, dst, *recursive); err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

func copyPath(src, dst string, recursive bool) error {
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	if info.IsDir() {
		if !recursive {
			return fmt.Errorf("%s is a directory (use -r)", src)
		}
		return copyDir(src, filepath.Join(dst, filepath.Base(src)))
	}
	dstInfo, err := os.Stat(dst)
	if err == nil && dstInfo.IsDir() {
		dst = filepath.Join(dst, filepath.Base(src))
	}
	return copyFile(src, dst)
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

func copyDir(src, dst string) error {
	if err := os.MkdirAll(dst, 0755); err != nil {
		return err
	}
	entries, err := os.ReadDir(src)
	if err != nil {
		return err
	}
	for _, e := range entries {
		srcPath := filepath.Join(src, e.Name())
		dstPath := filepath.Join(dst, e.Name())
		if e.IsDir() {
			if err := copyDir(srcPath, dstPath); err != nil {
				return err
			}
		} else {
			if err := copyFile(srcPath, dstPath); err != nil {
				return err
			}
		}
	}
	return nil
}

// ---- move ----

func printMoveUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s move <src> [src...] <dst>\n", progName)
}

func runMove(args []string) int {
	if len(args) < 2 {
		printMoveUsage()
		return 1
	}
	dst := args[len(args)-1]
	srcs := args[:len(args)-1]
	ok := true
	for _, src := range srcs {
		target := dst
		dstInfo, err := os.Stat(dst)
		if err == nil && dstInfo.IsDir() {
			target = filepath.Join(dst, filepath.Base(src))
		}
		if err := os.Rename(src, target); err != nil {
			// cross-device: copy then remove
			if err := copyPath(src, target, true); err != nil {
				fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
				ok = false
				continue
			}
			if err := os.RemoveAll(src); err != nil {
				fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
				ok = false
			}
		}
	}
	if !ok {
		return 1
	}
	return 0
}

// ---- remove ----

func printRemoveUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s remove [-r] [-f] <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  -r  Recursive (dirs)\n")
	fmt.Fprintf(os.Stderr, "  -f  Force (no error if missing)\n")
}

func runRemove(args []string) int {
	fs := flag.NewFlagSet("remove", flag.ExitOnError)
	recursive := fs.Bool("r", false, "Recursive")
	force := fs.Bool("f", false, "Force")
	fs.Usage = func() { printRemoveUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) == 0 {
		printRemoveUsage()
		return 1
	}
	ok := true
	for _, p := range paths {
		if err := removePath(p, *recursive, *force); err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

func removePath(path string, recursive, force bool) error {
	info, err := os.Stat(path)
	if err != nil {
		if os.IsNotExist(err) && force {
			return nil
		}
		return err
	}
	if info.IsDir() && !recursive {
		return fmt.Errorf("%s is a directory (use -r)", path)
	}
	if recursive {
		return os.RemoveAll(path)
	}
	return os.Remove(path)
}

// ---- mkdir ----

func printMkdirUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s mkdir [-p] <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  -p  Create parent dirs as needed\n")
}

func runMkdir(args []string) int {
	fs := flag.NewFlagSet("mkdir", flag.ExitOnError)
	parents := fs.Bool("p", false, "Parents")
	fs.Usage = func() { printMkdirUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}
	paths := fs.Args()
	if len(paths) == 0 {
		printMkdirUsage()
		return 1
	}
	ok := true
	for _, p := range paths {
		var err error
		if *parents {
			err = os.MkdirAll(p, 0755)
		} else {
			err = os.Mkdir(p, 0755)
		}
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

// ---- touch ----

func printTouchUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s touch <path>...\n", progName)
	fmt.Fprintf(os.Stderr, "  Create empty file or update mtime to now.\n")
}

func runTouch(args []string) int {
	if len(args) == 0 {
		printTouchUsage()
		return 1
	}
	now := time.Now()
	ok := true
	for _, p := range args {
		f, err := os.OpenFile(p, os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
			continue
		}
		f.Close()
		if err := os.Chtimes(p, now, now); err != nil {
			fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}
