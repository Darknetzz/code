# gohw

A command-line tool that displays hardware information about your computer with a visually styled output.

## Features

- **Motherboard** — Manufacturer, model, version
- **RAM** — Brand, capacity (GB), speed (MHz) per stick
- **CPU** — Brand, cores, threads, frequency (GHz)
- **GPU** — Name, VRAM, driver version
- **System** — Hostname, OS, platform, BIOS

## Build

```bash
go build -o gohw.exe .
```

## Usage

```bash
gohw.exe
```

## Platform Support

- **Windows** — Full hardware details via WMI (motherboard, RAM sticks, GPU, BIOS)
- **Linux / macOS** — Basic info via gopsutil (CPU, RAM total, host); motherboard/GPU details require Windows

## Output Example

```
  ⚙ SYSTEM INFORMATION  

╭─────────────────────────────────────────────────────────╮
│ Hostname:      desktop01                                │
│ OS:            windows 10.0.26200                       │
│ Platform:      Microsoft Windows 11 Enterprise / amd64  │
╰─────────────────────────────────────────────────────────╯

  ▸ Motherboard  
╭─────────────────────────────────╮
│ Board:          MSI MS-7E26 (1.0)│
╰─────────────────────────────────╯

  ▸ CPU  
╭──────────────────────────────────────────────────────────╮
│ Processor:     AMD Ryzen 7 7800X3D | 8 Cores 16 Threads │
│                | 4.20 GHz                                │
╰──────────────────────────────────────────────────────────╯
```

## Dependencies

- [gopsutil](https://github.com/shirou/gopsutil) — Cross-platform system info
- [StackExchange/wmi](https://github.com/StackExchange/wmi) — Windows WMI queries
- [lipgloss](https://github.com/charmbracelet/lipgloss) — Terminal styling
