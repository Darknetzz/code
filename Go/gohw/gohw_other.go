//go:build !windows

package main

import (
	"fmt"
	"os"
	"runtime"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
)

func main() {
	info, err := gatherInfoOther()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error gathering system info: %v\n", err)
		os.Exit(1)
	}
	renderOther(info)
}

type sysInfoOther struct {
	hostname   string
	os         string
	platform   string
	cpu        string
	cores      int
	threads    int
	ghz        float64
	ramTotalGB float64
}

func gatherInfoOther() (*sysInfoOther, error) {
	info := &sysInfoOther{}

	if h, err := host.Info(); err == nil {
		info.hostname = h.Hostname
		info.os = fmt.Sprintf("%s %s", h.OS, h.PlatformVersion)
		info.platform = h.Platform
	}

	if infos, err := cpu.Info(); err == nil && len(infos) > 0 {
		c := infos[0]
		info.cpu = strings.TrimSpace(c.ModelName)
		info.cores = int(c.Cores)
		info.ghz = c.Mhz / 1000
	}
	physicalCores, _ := cpu.Counts(false)
	logicalCores, _ := cpu.Counts(true)
	if physicalCores > 0 {
		info.cores = physicalCores
	}
	if logicalCores > 0 {
		info.threads = logicalCores
	}

	if v, err := mem.VirtualMemory(); err == nil {
		info.ramTotalGB = float64(v.Total) / (1024 * 1024 * 1024)
	}

	return info, nil
}

func renderOther(info *sysInfoOther) {
	accent := lipgloss.Color("#7D56F4")
	muted := lipgloss.Color("#6B7280")

	title := lipgloss.NewStyle().Bold(true).Foreground(accent).MarginBottom(1)
	const labelWidth = 14
	section := lipgloss.NewStyle().
		BorderStyle(lipgloss.RoundedBorder()).
		BorderForeground(accent).
		Padding(0, 1).
		MarginBottom(1)

	label := lipgloss.NewStyle().Foreground(muted)
	value := lipgloss.NewStyle().Foreground(lipgloss.Color("#E5E7EB"))

	row := func(k, v string) string {
		padded := fmt.Sprintf("%-*s", labelWidth, k+":")
		return label.Render(padded) + value.Render(v)
	}

	note := lipgloss.NewStyle().
		Foreground(muted).
		Italic(true).
		Render("Note: Full hardware details (motherboard, RAM sticks, GPU) require Windows.")

	var out strings.Builder
	out.WriteString(title.Render("  ⚙ SYSTEM INFORMATION  "))
	out.WriteString("\n\n")
	out.WriteString(section.Render(strings.Join([]string{
		row("Hostname", info.hostname),
		row("OS", info.os),
		row("Platform", info.platform+" / "+runtime.GOARCH),
		row("CPU", info.cpu),
		row("Cores/Threads", fmt.Sprintf("%d / %d", info.cores, info.threads)),
		row("Frequency", fmt.Sprintf("%.2f GHz", info.ghz)),
		row("RAM Total", fmt.Sprintf("%.2f GB", info.ramTotalGB)),
	}, "\n")))
	out.WriteString("\n\n")
	out.WriteString(note)
	out.WriteString("\n")

	fmt.Println(out.String())
}
