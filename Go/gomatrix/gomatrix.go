// gomatrix - Matrix digital rain in the terminal (movie-style characters).
package main

import (
	"fmt"
	"math/rand"
	"os"
	"os/signal"
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
	clearScreen = "\033[2J\033[H"
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
			y:     rand.Intn(h),
			length: 5 + rand.Intn(h/2),
			delay:  time.Duration(30+rand.Intn(120)) * time.Millisecond,
			last:   time.Now(),
		}
	}

	ticker := time.NewTicker(20 * time.Millisecond)
	defer ticker.Stop()

	for range ticker.C {
		fmt.Print(clearScreen)

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
				col.delay = time.Duration(30+rand.Intn(120)) * time.Millisecond
			}
		}

		// Build and print by row to avoid flicker
		grid := make([][]cell, h)
		for i := range grid {
			grid[i] = make([]cell, w)
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

		for row := 0; row < h; row++ {
			for col := 0; col < w; col++ {
				c := grid[row][col]
				if c.char == 0 {
					fmt.Print(" ")
					continue
				}
				if c.head {
					fmt.Printf("%s%c%s", greenBright, c.char, reset)
				} else {
					fmt.Printf("%s%c%s", greenDim, c.char, reset)
				}
			}
			if row < h-1 {
				fmt.Print("\n")
			}
		}
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
