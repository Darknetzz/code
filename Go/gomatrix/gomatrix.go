// gomatrix - Matrix digital rain in the terminal (movie-style characters).
package main

import (
	"bytes"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"strings"
	"time"

	"golang.org/x/term"
)

// Character sets: default is katakana only; optional digits and Latin.
var (
	charsKatakana = []rune("ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ")
	charsDigitsLatin = []rune("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
	activeChars []rune // set in main from -chars flag
)

const (
	version    = "1.0.0"
	reset      = "\033[0m"
	hideCursor = "\033[?25l"
	showCursor = "\033[?25h"
	cursorHome = "\033[H" // move to (1,1); overwrite instead of clear to avoid flicker
)

// ANSI bright and dim codes by color name (31=red, 32=green, 33=yellow, 34=blue, 35=magenta, 36=cyan, 37=white).
var colorCodes = map[string][2]string{
	"green":  {"\033[1;32m", "\033[2;32m"},
	"cyan":   {"\033[1;36m", "\033[2;36m"},
	"yellow": {"\033[1;33m", "\033[2;33m"},
	"red":    {"\033[1;31m", "\033[2;31m"},
	"blue":   {"\033[1;34m", "\033[2;34m"},
	"white":  {"\033[1;37m", "\033[2;37m"},
	"off":    {"", ""},
}

func main() {
	var speed float64
	var colorName, charsSet string
	var width, height, scale int
	speedUsage := "rain speed (e.g. 0.5 = half speed, 2 = twice as fast)"
	colorUsage := "color: green, cyan, yellow, red, blue, white, off"
	charsUsage := "chars: katakana (default), full (katakana+digits+latin), ascii (digits+latin only)"
	flag.Float64Var(&speed, "speed", 1, speedUsage)
	flag.Float64Var(&speed, "s", 1, speedUsage)
	flag.StringVar(&colorName, "color", "green", colorUsage)
	flag.StringVar(&colorName, "c", "green", colorUsage)
	flag.StringVar(&charsSet, "chars", "katakana", charsUsage)
	flag.StringVar(&charsSet, "charset", "katakana", charsUsage)
	flag.IntVar(&width, "width", 0, "grid width in columns (0 = terminal width)")
	flag.IntVar(&height, "height", 0, "grid height in rows (0 = terminal height)")
	flag.IntVar(&scale, "scale", 1, "character size: 1 = normal, 2 = double (each cell drawn 2x2)")
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Matrix digital rain in the terminal (movie-style characters). Version %s\n", version)
		fmt.Fprintln(os.Stderr, "Press Ctrl+C to exit.")
		fmt.Fprintln(os.Stderr)
		fmt.Fprintln(os.Stderr, "Options:")
		fmt.Fprintln(os.Stderr, "  -c, --color string")
		fmt.Fprintf(os.Stderr, "    \t%s (default %q)\n", colorUsage, "green")
		fmt.Fprintln(os.Stderr, "  --chars, --charset string")
		fmt.Fprintf(os.Stderr, "    \t%s (default %q)\n", charsUsage, "katakana")
		fmt.Fprintln(os.Stderr, "  --height int")
		fmt.Fprintf(os.Stderr, "    \t%s (default 0)\n", "grid height in rows (0 = terminal height)")
		fmt.Fprintln(os.Stderr, "  --scale int")
		fmt.Fprintf(os.Stderr, "    \t%s (default 1)\n", "character size: 1 = normal, 2 = double (each cell drawn 2x2)")
		fmt.Fprintln(os.Stderr, "  -s, --speed float")
		fmt.Fprintf(os.Stderr, "    \t%s (default 1)\n", speedUsage)
		fmt.Fprintln(os.Stderr, "  --width int")
		fmt.Fprintf(os.Stderr, "    \t%s (default 0)\n", "grid width in columns (0 = terminal width)")
	}
	flag.Parse()

	if scale != 1 && scale != 2 {
		fmt.Fprintln(os.Stderr, "gomatrix: --scale must be 1 or 2")
		os.Exit(1)
	}

	switch strings.ToLower(charsSet) {
	case "katakana":
		activeChars = charsKatakana
	case "full":
		activeChars = make([]rune, 0, len(charsKatakana)+len(charsDigitsLatin))
		activeChars = append(activeChars, charsKatakana...)
		activeChars = append(activeChars, charsDigitsLatin...)
	case "ascii":
		activeChars = charsDigitsLatin
	default:
		fmt.Fprintf(os.Stderr, "unknown -chars %q; use one of: katakana, full, ascii\n", charsSet)
		os.Exit(1)
	}

	codes, ok := colorCodes[strings.ToLower(colorName)]
	if !ok {
		fmt.Fprintf(os.Stderr, "unknown color %q; use one of: green, cyan, yellow, red, blue, white, off\n", colorName)
		os.Exit(1)
	}
	brightSeq, dimSeq := codes[0], codes[1]

	// Speed 1 = default "fast"; scale so delay = 1/(speed * defaultScale)
	const defaultSpeedScale = 2.5
	effectiveSpeed := speed * defaultSpeedScale
	speedFactor := 1.0 / effectiveSpeed
	if speedFactor <= 0 || speedFactor > 100 {
		speedFactor = 1.0
	}

	if !term.IsTerminal(int(os.Stdout.Fd())) {
		fmt.Fprintln(os.Stderr, "gomatrix: stdout is not a terminal")
		os.Exit(1)
	}

	fmt.Print(hideCursor)
	defer fmt.Print(showCursor)

	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt)
		<-sig
		fmt.Print(showCursor + reset + "\n")
		os.Exit(0)
	}()

	termW, termH := terminalSize()
	if termW <= 0 || termH <= 0 {
		termW, termH = 80, 24
	}
	w, h := termW, termH
	if width > 0 {
		w = min(width, termW)
	}
	if height > 0 {
		h = min(height, termH)
	}

	// With scale=2, simulate on half-size logical grid and draw each cell 2x2
	logW, logH := w, h
	if scale == 2 {
		logW = max(1, w/2)
		logH = max(1, h/2)
	}

	// Slower base delays = more relaxed rain
	baseMin, baseMax := 28, 75
	columns := make([]column, logW)
	for i := range columns {
		length := min(5+rand.Intn(max(1, logH/2)), logH)
		trail := make([]rune, length)
		for j := range trail {
			trail[j] = randMatrixChar()
		}
		columns[i] = column{
			y:       rand.Intn(logH),
			length:  length,
			delay:   columnDelay(baseMin, baseMax, speedFactor),
			last:    time.Now(),
			trail:   trail,
			headIdx: 0,
		}
	}

	// 20fps — fewer redraws often feels smoother when the terminal can't keep up
	ticker := time.NewTicker(50 * time.Millisecond)
	defer ticker.Stop()

	grid := make([][]cell, logH)
	for i := range grid {
		grid[i] = make([]cell, logW)
	}

	var buf bytes.Buffer
	buf.Grow(termW*h*24 + h*2 + 32)

	for range ticker.C {
		for x := 0; x < logW; x++ {
			col := &columns[x]
			if time.Since(col.last) < col.delay {
				continue
			}
			col.last = time.Now()
			col.y++
			// Circular buffer: no allocations on advance
			col.headIdx = (col.headIdx + col.length - 1) % col.length
			col.trail[col.headIdx] = randMatrixChar()
			if col.y-col.length > logH {
				col.y = 0
				col.length = min(5+rand.Intn(max(1, logH/2)), logH)
				col.delay = columnDelay(baseMin, baseMax, speedFactor)
				if len(col.trail) < col.length {
					col.trail = make([]rune, col.length)
				} else {
					col.trail = col.trail[:col.length]
				}
				for i := range col.trail {
					col.trail[i] = randMatrixChar()
				}
				col.headIdx = 0
			}
		}

		for row := 0; row < logH; row++ {
			for c := 0; c < logW; c++ {
				grid[row][c] = cell{}
			}
		}
		for x := 0; x < logW; x++ {
			col := &columns[x]
			for i := 0; i < col.length; i++ {
				row := col.y - i
				if row >= 0 && row < logH {
					idx := (col.headIdx + i) % col.length
					grid[row][x] = cell{char: col.trail[idx], head: i == 0}
				}
			}
		}

		// Reuse buffer to avoid allocating a large string every frame
		buf.Reset()
		buf.WriteString(cursorHome)
		for row := 0; row < h; row++ {
			logR := row / scale
			for c := 0; c < w; c++ {
				logC := c / scale
				ce := grid[logR][logC]
				if ce.char == 0 {
					buf.WriteByte(' ')
					continue
				}
				if ce.head {
					buf.WriteString(brightSeq)
				} else {
					buf.WriteString(dimSeq)
				}
				buf.WriteRune(ce.char)
				if brightSeq != "" || dimSeq != "" {
					buf.WriteString(reset)
				}
			}
			for c := w; c < termW; c++ {
				buf.WriteByte(' ')
			}
			buf.WriteByte('\n')
		}
		for row := h; row < termH; row++ {
			for c := 0; c < termW; c++ {
				buf.WriteByte(' ')
			}
			if row < termH-1 {
				buf.WriteByte('\n')
			}
		}
		buf.WriteTo(os.Stdout)
	}
}

type column struct {
	y       int
	length  int
	delay   time.Duration
	last    time.Time
	trail   []rune // pre-allocated, length = column length
	headIdx int    // circular buffer: head is at trail[headIdx]
}

type cell struct {
	char rune
	head bool
}

func columnDelay(baseMin, baseMax int, speedFactor float64) time.Duration {
	d := time.Duration(float64(baseMin+rand.Intn(baseMax))*speedFactor) * time.Millisecond
	if d < 8*time.Millisecond {
		d = 8 * time.Millisecond
	}
	return d
}

func randMatrixChar() rune {
	if len(activeChars) == 0 {
		return ' '
	}
	return activeChars[rand.Intn(len(activeChars))]
}

func terminalSize() (width, height int) {
	w, h, err := term.GetSize(int(os.Stdout.Fd()))
	if err != nil {
		return 80, 24
	}
	return w, h
}
