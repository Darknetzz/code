package main

import (
	"encoding/base64"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
)

// # Encode stdin
// "hello" | .\b64.exe
// # Decode
// "aGVsbG8=" | .\b64.exe -d

// # File in/out
// .\b64.exe -i in.bin -o out.txt
// .\b64.exe -d -i out.txt -o restored.bin

// # Positional file (input only)
// .\b64.exe secret.bin
// .\b64.exe -d -i encoded.txt

// # URL-safe (e.g. JWTs, query params)
// .\b64.exe -url -d -i token.txt

var progName string

func main() {
	progName = filepath.Base(os.Args[0])

	decode := flag.Bool("d", false, "Decode instead of encode")
	raw := flag.Bool("raw", false, "Use raw encoding (no padding)")
	url := flag.Bool("url", false, "Use URL-safe encoding")
	input := flag.String("i", "", "Input file (default: stdin)")
	output := flag.String("o", "", "Output file (default: stdout)")
	flag.Usage = func() {
		fmt.Fprintf(flag.CommandLine.Output(), "%s — base64 encode/decode\n\nUsage:\n  %s [options] [file]\n\n  With no file and no -i, reads from stdin.\n\nOptions:\n", progName, progName)
		flag.PrintDefaults()
	}
	flag.Parse()

	args := flag.Args()
	inPath := *input
	if inPath == "" && len(args) > 0 {
		inPath = args[0]
	}

	enc := chooseEncoding(*raw, *url)

	r, err := openInput(inPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		os.Exit(1)
	}
	defer closeIfCloser(r)

	w, err := openOutput(*output)
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		os.Exit(1)
	}
	defer closeIfCloser(w)

	if *decode {
		err = decodeStream(r, w, enc)
	} else {
		err = encodeStream(r, w, enc)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", progName, err)
		os.Exit(1)
	}
}

func chooseEncoding(raw, url bool) *base64.Encoding {
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
