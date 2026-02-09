// gomatrix - Matrix digital rain in the terminal (movie-style characters).
package main

import (
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
	speedUsage := "rain speed (e.g. 0.5 = half speed, 2 = twice as fast)"
	colorUsage := "color: green, cyan, yellow, red, blue, white, off"
	charsUsage := "chars: katakana (default), full (katakana+digits+latin), ascii (digits+latin only)"
	flag.Float64Var(&speed, "speed", 0.7, speedUsage)
	flag.Float64Var(&speed, "s", 0.7, speedUsage)
	flag.StringVar(&colorName, "color", "green", colorUsage)
	flag.StringVar(&colorName, "c", "green", colorUsage)
	flag.StringVar(&charsSet, "chars", "katakana", charsUsage)
	flag.StringVar(&charsSet, "charset", "katakana", charsUsage)
	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintln(os.Stderr, "Matrix digital rain in the terminal (movie-style characters).")
		fmt.Fprintln(os.Stderr, "Press Ctrl+C to exit.")
		fmt.Fprintln(os.Stderr)
		fmt.Fprintln(os.Stderr, "Options:")
		fmt.Fprintln(os.Stderr, "  -c, --color string")
		fmt.Fprintf(os.Stderr, "    \t%s (default %q)\n", colorUsage, "green")
		fmt.Fprintln(os.Stderr, "  --chars, --charset string")
		fmt.Fprintf(os.Stderr, "    \t%s (default %q)\n", charsUsage, "katakana")
		fmt.Fprintln(os.Stderr, "  -s, --speed float")
		fmt.Fprintf(os.Stderr, "    \t%s (default 0.7)\n", speedUsage)
	}
	flag.Parse()

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

	// Speed factor: delay is multiplied by 1/speed so speed=0.5 => slower
	speedFactor := 1.0 / speed
	if speedFactor <= 0 || speedFactor > 100 {
		speedFactor = 1.0
	}

	rand.Seed(time.Now().UnixNano())

	fmt.Print(hideCursor)
	defer fmt.Print(showCursor)

	go func() {
		sig := make(chan os.Signal, 1)
		signal.Notify(sig, os.Interrupt)
		<-sig
		fmt.Print(showCursor + reset + "\n")
		os.Exit(0)
	}()

	w, h := terminalSize()
	if w <= 0 || h <= 0 {
		w, h = 80, 24
	}

	// Slower base delays = more relaxed rain; 60fps tick for smoother redraws
	baseMin, baseMax := 28, 75
	columns := make([]column, w)
	for i := range columns {
		d := time.Duration(float64(baseMin+rand.Intn(baseMax)) * speedFactor) * time.Millisecond
		if d < 8*time.Millisecond {
			d = 8 * time.Millisecond
		}
		columns[i] = column{
			y:      rand.Intn(h),
			length: 5 + rand.Intn(h/2),
			delay:  d,
			last:   time.Now(),
		}
	}

	ticker := time.NewTicker(16 * time.Millisecond) // ~60fps for smoother animation
	defer ticker.Stop()

	grid := make([][]cell, h)
	for i := range grid {
		grid[i] = make([]cell, w)
	}

	for range ticker.C {
		for x := 0; x < w; x++ {
			col := &columns[x]
			if time.Since(col.last) < col.delay {
				continue
			}
			col.last = time.Now()
			col.y++
			if col.y-col.length > h {
				col.y = 0
				col.length = 5 + rand.Intn(h/2)
				d := time.Duration(float64(baseMin+rand.Intn(baseMax)) * speedFactor) * time.Millisecond
				if d < 8*time.Millisecond {
					d = 8 * time.Millisecond
				}
				col.delay = d
			}
		}

		for row := 0; row < h; row++ {
			for c := 0; c < w; c++ {
				grid[row][c] = cell{}
			}
		}
		for x := 0; x < w; x++ {
			col := &columns[x]
			for i := 0; i < col.length; i++ {
				row := col.y - i
				if row >= 0 && row < h {
					head := i == 0
					grid[row][x] = cell{char: randMatrixChar(), head: head}
				}
			}
		}

		var sb strings.Builder
		sb.Grow(w*h*20 + h + 8)
		sb.WriteString(cursorHome)
		for row := 0; row < h; row++ {
			for c := 0; c < w; c++ {
				cell := grid[row][c]
				if cell.char == 0 {
					sb.WriteByte(' ')
					continue
				}
				if cell.head {
					sb.WriteString(brightSeq)
				} else {
					sb.WriteString(dimSeq)
				}
				sb.WriteString(string(cell.char))
				if brightSeq != "" || dimSeq != "" {
					sb.WriteString(reset)
				}
			}
			if row < h-1 {
				sb.WriteByte('\n')
			}
		}
		os.Stdout.WriteString(sb.String())
	}
}

type column struct {
	y      int
	length int
	delay  time.Duration
	last   time.Time
}

type cell struct {
	char rune
	head bool
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
