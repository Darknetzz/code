//go:build windows

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
	"github.com/StackExchange/wmi"
)

// WMI structs for Windows hardware info (field names must match WMI exactly)
type win32BaseBoard struct {
	Manufacturer string
	Product      string
	Version      string
	SerialNumber string
}

type win32PhysicalMemory struct {
	Manufacturer       string
	Capacity          uint64
	Speed             uint32
	ConfiguredClockSpeed uint32
	PartNumber        string
}

type win32Processor struct {
	Name                      string
	NumberOfCores             uint32
	NumberOfLogicalProcessors uint32
	MaxClockSpeed             uint32
}

type win32VideoController struct {
	Name        string
	AdapterRAM  uint32
	DriverVersion string
}

type win32BIOS struct {
	Manufacturer string
	SMBIOSBIOSVersion string
	ReleaseDate string
}

type sysInfo struct {
	hostname    string
	os          string
	platform    string
	bios        string
	motherboard string
	cpu         string
	cores       int
	threads     int
	ghz         float64
	ram         []ramStick
	ramTotalGB  float64
	gpus        []gpuInfo
}

type ramStick struct {
	brand string
	gb    float64
	mhz   uint32
}

type gpuInfo struct {
	name    string
	vramGB  float64
	driver  string
}

func main() {
	info, err := gatherInfo()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error gathering system info: %v\n", err)
		os.Exit(1)
	}
	render(info)
}

func gatherInfo() (*sysInfo, error) {
	info := &sysInfo{}

	// Allow WMI structs to have extra fields not returned by query
	wmi.DefaultClient.AllowMissingFields = true

	// Host info (gopsutil - cross-platform)
	if h, err := host.Info(); err == nil {
		info.hostname = h.Hostname
		info.os = fmt.Sprintf("%s %s", h.OS, h.PlatformVersion)
		info.platform = h.Platform
	}

	// CPU (gopsutil for cores/threads, WMI for name/speed)
	if infos, err := cpu.Info(); err == nil && len(infos) > 0 {
		c := infos[0]
		info.cpu = strings.TrimSpace(c.ModelName)
		if info.cpu == "" {
			info.cpu = "Unknown"
		}
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

	// WMI: Processor (override/fallback)
	var procs []win32Processor
	if err := wmi.Query(wmi.CreateQuery(&procs, "", "Win32_Processor"), &procs); err == nil && len(procs) > 0 {
		p := procs[0]
		if p.Name != "" {
			info.cpu = strings.TrimSpace(p.Name)
		}
		if p.NumberOfCores > 0 {
			info.cores = int(p.NumberOfCores)
		}
		if p.NumberOfLogicalProcessors > 0 {
			info.threads = int(p.NumberOfLogicalProcessors)
		}
		if p.MaxClockSpeed > 0 {
			info.ghz = float64(p.MaxClockSpeed) / 1000
		}
	}

	// WMI: Motherboard
	var boards []win32BaseBoard
	if err := wmi.Query(wmi.CreateQuery(&boards, "", "Win32_BaseBoard"), &boards); err == nil && len(boards) > 0 {
		b := boards[0]
		parts := []string{}
		if b.Manufacturer != "" {
			parts = append(parts, strings.TrimSpace(b.Manufacturer))
		}
		if b.Product != "" {
			parts = append(parts, strings.TrimSpace(b.Product))
		}
		if b.Version != "" {
			parts = append(parts, "("+strings.TrimSpace(b.Version)+")")
		}
		info.motherboard = strings.Join(parts, " ")
		if info.motherboard == "" {
			info.motherboard = "Unknown"
		}
	}

	// WMI: BIOS
	var biosList []win32BIOS
	if err := wmi.Query(wmi.CreateQuery(&biosList, "", "Win32_BIOS"), &biosList); err == nil && len(biosList) > 0 {
		b := biosList[0]
		parts := []string{}
		if b.Manufacturer != "" {
			parts = append(parts, strings.TrimSpace(b.Manufacturer))
		}
		if b.SMBIOSBIOSVersion != "" {
			parts = append(parts, strings.TrimSpace(b.SMBIOSBIOSVersion))
		}
		if b.ReleaseDate != "" {
			parts = append(parts, "("+strings.TrimSpace(b.ReleaseDate)+")")
		}
		info.bios = strings.Join(parts, " ")
	}

	// WMI: Physical Memory
	var memList []win32PhysicalMemory
	if err := wmi.Query(wmi.CreateQuery(&memList, "", "Win32_PhysicalMemory"), &memList); err == nil {
		var total uint64
		for _, m := range memList {
			gb := float64(m.Capacity) / (1024 * 1024 * 1024)
			total += m.Capacity
			speed := m.Speed
			if speed == 0 {
				speed = m.ConfiguredClockSpeed
			}
			brand := strings.TrimSpace(m.Manufacturer)
			if brand == "" {
				brand = "Unknown"
			}
			info.ram = append(info.ram, ramStick{brand: brand, gb: gb, mhz: speed})
		}
		info.ramTotalGB = float64(total) / (1024 * 1024 * 1024)
	}

	// Fallback: gopsutil memory if WMI didn't return RAM
	if info.ramTotalGB == 0 {
		if v, err := mem.VirtualMemory(); err == nil {
			info.ramTotalGB = float64(v.Total) / (1024 * 1024 * 1024)
			info.ram = []ramStick{{brand: "—", gb: info.ramTotalGB, mhz: 0}}
		}
	}

	// WMI: Video controllers
	var videos []win32VideoController
	if err := wmi.Query(wmi.CreateQuery(&videos, "", "Win32_VideoController"), &videos); err == nil {
		for _, v := range videos {
			name := strings.TrimSpace(v.Name)
			if name == "" {
				name = "Unknown"
			}
			// Skip Microsoft Basic Display Adapter only when we have other GPUs
			if strings.Contains(name, "Microsoft Basic") && len(videos) > 1 {
				continue
			}
			vramBytes := uint64(v.AdapterRAM)
			// AdapterRAM can be 0xFFFFFFFF or wrong for WDDM - treat as unknown
			if vramBytes == 0 || vramBytes >= 0x80000000 {
				vramBytes = 0
			}
			vramGB := float64(vramBytes) / (1024 * 1024 * 1024)
			info.gpus = append(info.gpus, gpuInfo{
				name:   name,
				vramGB: vramGB,
				driver: strings.TrimSpace(v.DriverVersion),
			})
		}
	}

	return info, nil
}

func formatBytes(gb float64) string {
	if gb < 0.01 {
		return "—"
	}
	return fmt.Sprintf("%.2f GB", gb)
}

func render(info *sysInfo) {
	accent := lipgloss.Color("#7D56F4")
	muted := lipgloss.Color("#6B7280")
	title := lipgloss.NewStyle().
		Bold(true).
		Foreground(accent).
		MarginBottom(1)

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

	var out strings.Builder

	// Header
	out.WriteString(title.Render("  ⚙ SYSTEM INFORMATION  "))
	out.WriteString("\n\n")

	// System
	sysLines := []string{
		row("Hostname", info.hostname),
		row("OS", info.os),
		row("Platform", info.platform+" / "+runtime.GOARCH),
	}
	if info.bios != "" {
		sysLines = append(sysLines, row("BIOS", info.bios))
	}
	out.WriteString(section.Render(strings.Join(sysLines, "\n")))
	out.WriteString("\n\n")

	// Motherboard
	out.WriteString(title.Render("  ▸ Motherboard  "))
	out.WriteString(section.Render(row("Board", info.motherboard)))
	out.WriteString("\n\n")

	// CPU
	cpuStr := info.cpu
	if info.threads > 0 {
		cpuStr += fmt.Sprintf("  |  %d Cores  %d Threads", info.cores, info.threads)
	}
	if info.ghz > 0 {
		cpuStr += fmt.Sprintf("  |  %.2f GHz", info.ghz)
	}
	out.WriteString(title.Render("  ▸ CPU  "))
	out.WriteString(section.Render(row("Processor", cpuStr)))
	out.WriteString("\n\n")

	// RAM
	var ramLines []string
	if len(info.ram) == 0 {
		ramLines = []string{row("Total", fmt.Sprintf("%.2f GB", info.ramTotalGB))}
	} else if len(info.ram) == 1 {
		r := info.ram[0]
		stick := formatBytes(r.gb)
		if r.brand != "—" {
			stick += "  " + r.brand
		}
		if r.mhz > 0 {
			stick += fmt.Sprintf("  @ %d MHz", r.mhz)
		}
		ramLines = []string{row("Total", stick)}
	} else if len(info.ram) > 1 {
		ramLines = []string{row("Total", fmt.Sprintf("%.2f GB", info.ramTotalGB))}
		for i, r := range info.ram {
			stick := formatBytes(r.gb)
			if r.brand != "—" {
				stick += "  " + r.brand
			}
			if r.mhz > 0 {
				stick += fmt.Sprintf("  @ %d MHz", r.mhz)
			}
			ramLines = append(ramLines, row(fmt.Sprintf("Stick %d", i+1), stick))
		}
	}
	out.WriteString(title.Render("  ▸ RAM  "))
	out.WriteString(section.Render(strings.Join(ramLines, "\n")))
	out.WriteString("\n\n")

	// GPU
	out.WriteString(title.Render("  ▸ GPU  "))
	if len(info.gpus) == 0 {
		out.WriteString(section.Render(row("Adapter", "No GPU information available")))
	}
	for i, g := range info.gpus {
		gpuStr := g.name
		if g.vramGB > 0 {
			gpuStr += fmt.Sprintf("  |  %s VRAM", formatBytes(g.vramGB))
		}
		if g.driver != "" {
			gpuStr += fmt.Sprintf("  |  Driver %s", g.driver)
		}
		var gpuLines []string
		if len(info.gpus) > 1 {
			gpuLines = []string{row(fmt.Sprintf("GPU %d", i+1), gpuStr)}
		} else {
			gpuLines = []string{row("Adapter", gpuStr)}
		}
		out.WriteString(section.Render(strings.Join(gpuLines, "\n")))
		if i < len(info.gpus)-1 {
			out.WriteString("\n")
		}
	}

	fmt.Println(out.String())
}
