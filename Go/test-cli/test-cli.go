package main

import (
	"bufio"
	"crypto/md5"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/sha512"
	"encoding/hex"
	"flag"
	"fmt"
	"hash"
	"io"
	"os"
	"strings"
)

const usage = `test-cli — file checksum (hash) utility

Usage:
  test-cli [options] [file...]

Options:
`

func main() {
	algo := flag.String("a", "sha256", "Hash algorithm: md5, sha1, sha256, sha512")
	quiet := flag.Bool("q", false, "Quiet: print only the hash")
	check := flag.String("c", "", "Verify hashes from FILE (one line per \"hash  path\")")
	flag.Usage = func() {
		fmt.Fprint(flag.CommandLine.Output(), usage)
		flag.PrintDefaults()
	}
	flag.Parse()

	if *check != "" {
		os.Exit(runCheck(*check, *algo, *quiet))
	}

	args := flag.Args()
	if len(args) == 0 {
		hashStdin(*algo, *quiet)
		return
	}

	ok := true
	for _, path := range args {
		if err := hashFile(path, *algo, *quiet); err != nil {
			fmt.Fprintf(os.Stderr, "test-cli: %v\n", err)
			ok = false
		}
	}
	if !ok {
		os.Exit(1)
	}
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
		fmt.Fprintf(os.Stderr, "test-cli: %v\n", err)
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

func runCheck(checkPath, algo string, quiet bool) int {
	f, err := os.Open(checkPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "test-cli: %v\n", err)
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
			fmt.Fprintf(os.Stderr, "test-cli: %s: %v\n", path, err)
			failed++
			continue
		}
		got, err := hashReader(file, algo)
		file.Close()
		if err != nil {
			fmt.Fprintf(os.Stderr, "test-cli: %s: %v\n", path, err)
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
		fmt.Fprintf(os.Stderr, "test-cli: %v\n", err)
		return 1
	}
	if failed > 0 {
		return 1
	}
	return 0
}
