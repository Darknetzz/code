package main

import (
	"bufio"
	"crypto/md5"
	"crypto/rand"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/base64"
	"encoding/hex"
	"flag"
	"fmt"
	"hash"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// Usage:
//   gotools                    — list commands
//   gotools b64 [options] [file]
//   gotools hash [options] [file...]
//   gotools uuid [n]

var progName string

func main() {
	progName = filepath.Base(os.Args[0])
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(0)
	}

	cmd := strings.ToLower(os.Args[1])
	args := os.Args[2:]

	switch cmd {
	case "b64", "base64":
		os.Exit(runB64(args))
	case "hash", "checksum":
		os.Exit(runHash(args))
	case "uuid":
		os.Exit(runUUID(args))
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
}

func printUsage() {
	fmt.Fprintf(os.Stderr, "%s — general-purpose CLI tools\n\n", progName)
	fmt.Fprintf(os.Stderr, "Usage:\n  %s <command> [options] [args]\n\n", progName)
	fmt.Fprintf(os.Stderr, "Commands:\n")
	fmt.Fprintf(os.Stderr, "  b64       Base64 encode/decode (stdin or file)\n")
	fmt.Fprintf(os.Stderr, "  hash      File checksums (md5, sha1, sha256, sha512)\n")
	fmt.Fprintf(os.Stderr, "  uuid      Generate random UUIDs\n")
	fmt.Fprintf(os.Stderr, "\n  %s help <command>  — help for a command\n", progName)
}

func printCommandHelp(cmd string) {
	switch strings.ToLower(cmd) {
	case "b64", "base64":
		printB64Usage()
	case "hash", "checksum":
		printHashUsage()
	case "uuid":
		printUUIDUsage()
	default:
		fmt.Fprintf(os.Stderr, "%s: unknown command %q\n", progName, cmd)
	}
}

// ---- I/O helpers (shared) ----

func openInput(path string) (io.Reader, error) {
	if path == "" {
		return os.Stdin, nil
	}
	return os.Open(path)
}

func openOutput(path string) (io.Writer, error) {
	if path == "" {
		return os.Stdout, nil
	}
	return os.Create(path)
}

func closeIfCloser(x interface{}) {
	c, ok := x.(io.Closer)
	if !ok {
		return
	}
	if f, ok := c.(*os.File); ok && (f == os.Stdin || f == os.Stdout) {
		return
	}
	c.Close()
}

// ---- b64 ----

func printB64Usage() {
	fmt.Fprintf(os.Stderr, "Usage: %s b64 [options] [file]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Encode (default) or decode base64. Input: file, or stdin if no file.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -d       Decode instead of encode\n")
	fmt.Fprintf(os.Stderr, "  -i path  Input file\n")
	fmt.Fprintf(os.Stderr, "  -o path  Output file\n")
	fmt.Fprintf(os.Stderr, "  -raw     Raw encoding (no padding)\n")
	fmt.Fprintf(os.Stderr, "  -url     URL-safe encoding\n")
}

func runB64(args []string) int {
	fs := flag.NewFlagSet("b64", flag.ExitOnError)
	decode := fs.Bool("d", false, "Decode instead of encode")
	raw := fs.Bool("raw", false, "Use raw encoding (no padding)")
	url := fs.Bool("url", false, "Use URL-safe encoding")
	input := fs.String("i", "", "Input file")
	output := fs.String("o", "", "Output file")
	fs.Usage = func() { printB64Usage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}

	inPath := *input
	if inPath == "" && len(fs.Args()) > 0 {
		inPath = fs.Args()[0]
	}

	enc := chooseB64Encoding(*raw, *url)
	r, err := openInput(inPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s b64: %v\n", progName, err)
		return 1
	}
	defer closeIfCloser(r)

	w, err := openOutput(*output)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s b64: %v\n", progName, err)
		return 1
	}
	defer closeIfCloser(w)

	if *decode {
		err = decodeStream(r, w, enc)
	} else {
		err = encodeStream(r, w, enc)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s b64: %v\n", progName, err)
		return 1
	}
	return 0
}

func chooseB64Encoding(raw, url bool) *base64.Encoding {
	if url {
		if raw {
			return base64.RawURLEncoding
		}
		return base64.URLEncoding
	}
	if raw {
		return base64.RawStdEncoding
	}
	return base64.StdEncoding
}

func encodeStream(r io.Reader, w io.Writer, enc *base64.Encoding) error {
	encW := base64.NewEncoder(enc, w)
	_, err := io.Copy(encW, r)
	if closeErr := encW.Close(); err == nil {
		err = closeErr
	}
	return err
}

func decodeStream(r io.Reader, w io.Writer, enc *base64.Encoding) error {
	dec := base64.NewDecoder(enc, r)
	_, err := io.Copy(w, dec)
	return err
}

// ---- hash ----

func printHashUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s hash [options] [file...]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Print checksums. With no files, hash stdin.\n\n")
	fmt.Fprintf(os.Stderr, "Options:\n")
	fmt.Fprintf(os.Stderr, "  -a algo   Algorithm: md5, sha1, sha256, sha512 (default: sha256)\n")
	fmt.Fprintf(os.Stderr, "  -c file   Verify checksums from file (one 'hash  path' per line)\n")
	fmt.Fprintf(os.Stderr, "  -q        Quiet: print only the hash\n")
}

func runHash(args []string) int {
	fs := flag.NewFlagSet("hash", flag.ExitOnError)
	algo := fs.String("a", "sha256", "Hash algorithm")
	quiet := fs.Bool("q", false, "Quiet")
	check := fs.String("c", "", "Verify hashes from file")
	fs.Usage = func() { printHashUsage() }
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if *check != "" {
		return runHashCheck(*check, *algo, *quiet)
	}

	if len(fs.Args()) == 0 {
		hashStdin(*algo, *quiet)
		return 0
	}

	ok := true
	for _, path := range fs.Args() {
		if err := hashFile(path, *algo, *quiet); err != nil {
			fmt.Fprintf(os.Stderr, "%s hash: %v\n", progName, err)
			ok = false
		}
	}
	if !ok {
		return 1
	}
	return 0
}

func hashFile(path, algo string, quiet bool) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	sum, err := hashReader(f, algo)
	if err != nil {
		return err
	}
	if quiet {
		fmt.Println(sum)
	} else {
		fmt.Printf("%s  %s\n", sum, path)
	}
	return nil
}

func hashStdin(algo string, quiet bool) {
	sum, err := hashReader(os.Stdin, algo)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s hash: %v\n", progName, err)
		os.Exit(1)
	}
	if quiet {
		fmt.Println(sum)
	} else {
		fmt.Printf("%s  -\n", sum)
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

func newHasher(algo string) (hash.Hash, error) {
	switch strings.ToLower(algo) {
	case "md5":
		return md5.New(), nil
	case "sha1":
		return sha1.New(), nil
	case "sha256":
		return sha256.New(), nil
	case "sha512":
		return sha512.New(), nil
	default:
		return nil, fmt.Errorf("unknown algorithm %q (use: md5, sha1, sha256, sha512)", algo)
	}
}

func runHashCheck(checkPath, algo string, quiet bool) int {
	f, err := os.Open(checkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s hash: %v\n", progName, err)
		return 1
	}
	defer f.Close()

	var failed int
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}
		want, path := parts[0], parts[1]
		file, err := os.Open(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %s: %v\n", progName, path, err)
			failed++
			continue
		}
		got, err := hashReader(file, algo)
		file.Close()
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s: %s: %v\n", progName, path, err)
			failed++
			continue
		}
		if got != want {
			if !quiet {
				fmt.Printf("%s: FAILED\n", path)
			}
			failed++
		} else if !quiet {
			fmt.Printf("%s: OK\n", path)
		}
	}
	if err := sc.Err(); err != nil {
		fmt.Fprintf(os.Stderr, "%s hash: %v\n", progName, err)
		return 1
	}
	if failed > 0 {
		return 1
	}
	return 0
}

// ---- uuid ----

func printUUIDUsage() {
	fmt.Fprintf(os.Stderr, "Usage: %s uuid [n]\n\n", progName)
	fmt.Fprintf(os.Stderr, "  Generate random UUIDs (v4). Optional n = count (default 1).\n")
}

func runUUID(args []string) int {
	n := 1
	if len(args) > 0 {
		if _, err := fmt.Sscanf(args[0], "%d", &n); err != nil || n < 1 {
			fmt.Fprintf(os.Stderr, "%s uuid: invalid count %q\n", progName, args[0])
			return 1
		}
	}
	for i := 0; i < n; i++ {
		u, err := uuidV4()
		if err != nil {
			fmt.Fprintf(os.Stderr, "%s uuid: %v\n", progName, err)
			return 1
		}
		fmt.Println(u)
	}
	return 0
}

func uuidV4() (string, error) {
	var b [16]byte
	if _, err := rand.Read(b[:]); err != nil {
		return "", err
	}
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		b[0:4], b[4:6], b[6:8], b[8:10], b[10:16]), nil
}
