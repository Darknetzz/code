// gomatrix - Matrix digital rain in the terminal (movie-style characters).
package main

import (
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"strings"
	"time"

	"golang.org/x/term"
)

// Matrix-style character set: katakana (half-width), digits, and Latin — like the movie.
var matrixChars = []rune(
	// Half-width katakana (movie-style)
	"ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ" +
		// Digits and Latin
		"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
)

const (
	greenBright = "\033[1;32m" // Bright green (head of column)
	greenDim    = "\033[2;32m" // Dim green (trail)
	reset       = "\033[0m"
	hideCursor  = "\033[?25l"
	showCursor  = "\033[?25h"
	cursorHome = "\033[H" // move to (1,1); overwrite instead of clear to avoid flicker
)

func main() {
	rand.Seed(time.Now().UnixNano())

	// Raw terminal / hide cursor
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

	// One column per screen column; each has its own length and delay
	columns := make([]column, w)
	for i := range columns {
		columns[i] = column{
			y:      rand.Intn(h),
			length: 5 + rand.Intn(h/2),
			delay:  time.Duration(15+rand.Intn(50)) * time.Millisecond, // faster step = smoother motion
			last:   time.Now(),
		}
	}

	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()

	// Reuse grid to avoid allocations every frame
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
				col.delay = time.Duration(15+rand.Intn(50)) * time.Millisecond
			}
		}

		// Clear and fill grid (reuse)
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

		// Build entire frame in one buffer, then single write (smoother)
		var sb strings.Builder
		sb.Grow(w*h*20 + h + 8) // rough: ~20 bytes per cell, newlines, cursor
		sb.WriteString(cursorHome)
		for row := 0; row < h; row++ {
			for c := 0; c < w; c++ {
				cell := grid[row][c]
				if cell.char == 0 {
					sb.WriteByte(' ')
					continue
				}
				if cell.head {
					sb.WriteString(greenBright)
				} else {
					sb.WriteString(greenDim)
				}
				sb.WriteString(string(cell.char))
				sb.WriteString(reset)
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
	if len(matrixChars) == 0 {
		return ' '
	}
	return matrixChars[rand.Intn(len(matrixChars))]
}

func terminalSize() (width, height int) {
	w, h, err := term.GetSize(int(os.Stdout.Fd()))
	if err != nil {
		return 80, 24
	}
	return w, h
}
