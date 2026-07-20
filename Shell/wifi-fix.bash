#!/usr/bin/env bash
# Wi-Fi fix for freezes/disconnects (tuned for MediaTek MT7922 / mt7921e).
# Escalates: unblock → interface bounce → module reload → PCI reset → remove/rescan.
#
# Usage:
#   sudo ./wifi-fix.bash              # interactive prompts for anything unspecified
#   sudo ./wifi-fix.bash --yes        # non-interactive: auto-pick defaults, full recover
#   sudo ./wifi-fix.bash --quick       # stop after module reload
#   sudo ./wifi-fix.bash --status     # show current Wi-Fi state
#   sudo ./wifi-fix.bash --logs       # dump recent kernel Wi-Fi logs
#   sudo ./wifi-fix.bash --iface wlp1s0 --module mt7921e --pci 0000:01:00.0

set -euo pipefail

IFACE="${WIFI_IFACE:-}"
MODULE="${WIFI_MODULE:-}"
PCI_DEV="${WIFI_PCI:-}"
CONNECTION="${WIFI_CONNECTION:-}"
LOG_TAG="wifi-fix"
QUICK=""
MODE=""
ASSUME_YES=0

usage() {
  awk 'NR==1 {next} /^#/ {sub(/^# ?/,""); print; next} {exit}' "$0"
  exit "${1:-0}"
}

log() {
  local msg="$*"
  printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$msg"
  logger -t "$LOG_TAG" -- "$msg" 2>/dev/null || true
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

need_root() {
  [[ "$(id -u)" -eq 0 ]] || die "Run as root (sudo $0)"
}

can_prompt() {
  [[ "$ASSUME_YES" -eq 0 && -t 0 && -t 1 ]]
}

# prompt_choice "Question" "default_index_1based" "opt1" "opt2" ...
# Prints selected value on stdout. Options are 1-based in the UI.
prompt_choice() {
  local question="$1"
  local default="$2"
  shift 2
  local opts=("$@")
  local count="${#opts[@]}"
  local i reply

  [[ "$count" -gt 0 ]] || die "No options available for: $question"

  if [[ "$count" -eq 1 ]]; then
    if can_prompt; then
      printf '%s\n  [1] %s (only option)\n' "$question" "${opts[0]}" >&2
      read -r -p "Press Enter to accept [1]: " reply || true
    fi
    printf '%s\n' "${opts[0]}"
    return 0
  fi

  if ! can_prompt; then
    local idx=$((default - 1))
    [[ "$idx" -ge 0 && "$idx" -lt "$count" ]] || idx=0
    printf 'Auto-selected: %s\n' "${opts[$idx]}" >&2
    printf '%s\n' "${opts[$idx]}"
    return 0
  fi

  printf '%s\n' "$question" >&2
  for ((i = 0; i < count; i++)); do
    printf '  [%d] %s\n' "$((i + 1))" "${opts[$i]}" >&2
  done
  while true; do
    read -r -p "Choice [${default}]: " reply || true
    reply="${reply:-$default}"
    if [[ "$reply" =~ ^[0-9]+$ ]] && ((reply >= 1 && reply <= count)); then
      printf '%s\n' "${opts[$((reply - 1))]}"
      return 0
    fi
    printf 'Invalid choice. Enter 1-%d.\n' "$count" >&2
  done
}

prompt_confirm() {
  local question="$1"
  local default="${2:-y}" # y|n
  local reply
  if ! can_prompt; then
    [[ "$default" == "y" ]]
    return $?
  fi
  if [[ "$default" == "y" ]]; then
    read -r -p "$question [Y/n]: " reply || true
    reply="${reply:-y}"
  else
    read -r -p "$question [y/N]: " reply || true
    reply="${reply:-n}"
  fi
  [[ "${reply,,}" == "y" || "${reply,,}" == "yes" ]]
}

iface_exists() {
  [[ -n "$IFACE" && -d "/sys/class/net/$IFACE" ]]
}

pci_exists() {
  [[ -n "$PCI_DEV" && -d "/sys/bus/pci/devices/$PCI_DEV" ]]
}

nm_available() {
  command -v nmcli >/dev/null 2>&1
}

wait_for() {
  local seconds="$1"
  shift
  local i
  for ((i = 0; i < seconds; i++)); do
    if "$@"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wifi_associated() {
  iface_exists || return 1
  command -v iw >/dev/null 2>&1 || return 1
  iw dev "$IFACE" link 2>/dev/null | grep -q 'Connected to'
}

# --- Discovery ------------------------------------------------------------

discover_ifaces() {
  local found=()
  local iface type
  if nm_available; then
    while IFS=: read -r iface type _; do
      [[ "$type" == "wifi" ]] || continue
      found+=("$iface")
    done < <(nmcli -t -f DEVICE,TYPE device status 2>/dev/null || true)
  fi
  # Fallback: wireless sysfs / common names
  if [[ "${#found[@]}" -eq 0 ]]; then
    for iface in /sys/class/net/*; do
      iface="${iface##*/}"
      [[ -d "/sys/class/net/$iface/wireless" || -d "/sys/class/net/$iface/phy80211" ]] || continue
      found+=("$iface")
    done
  fi
  if [[ "${#found[@]}" -eq 0 ]]; then
    for iface in /sys/class/net/wl* /sys/class/net/wlan*; do
      [[ -e "$iface" ]] || continue
      found+=("${iface##*/}")
    done
  fi
  printf '%s\n' "${found[@]}"
}

discover_pci() {
  local line addr desc
  while IFS= read -r line; do
    addr="${line%% *}"
    desc="${line#* }"
    printf '%s  —  %s\n' "$addr" "$desc"
  done < <(lspci -Dnn 2>/dev/null | grep -iE 'Network controller|Wireless|Wi-Fi|WLAN' || true)
}

discover_modules_for_pci() {
  local pci="$1"
  local driver path
  path="/sys/bus/pci/devices/$pci"
  if [[ -L "$path/driver" ]]; then
    driver="$(basename "$(readlink -f "$path/driver")")"
    [[ -n "$driver" ]] && printf '%s\n' "$driver"
  fi
  # Common wireless drivers as extras
  local m
  for m in mt7921e mt7921u iwlwifi ath11k_pci ath10k_pci rtw89_8852ce rtw88_8822ce; do
    modinfo "$m" >/dev/null 2>&1 || continue
    printf '%s\n' "$m"
  done | awk 'NF && !seen[$0]++'
}

discover_loaded_wifi_modules() {
  lsmod 2>/dev/null | awk '
    $1 ~ /^(mt7921e|mt7921u|iwlwifi|ath11k_pci|ath10k_pci|rtw89_|rtw88_|brcmfmac|mwifiex_pcie)/ { print $1 }
  ' | awk 'NF && !seen[$0]++'
}

discover_connections() {
  nm_available || return 0
  nmcli -t -f NAME,TYPE connection show 2>/dev/null \
    | awk -F: '$2 == "802-11-wireless" { print $1 }'
}

iface_label() {
  local iface="$1" state=""
  state="$(ip -br link show "$iface" 2>/dev/null | awk '{print $2}')"
  if [[ -n "$state" ]]; then
    printf '%s — %s' "$iface" "$state"
  else
    printf '%s' "$iface"
  fi
}

# Strip "value — description" labels back to the value.
label_value() {
  local s="$1"
  if [[ "$s" == *" — "* ]]; then
    printf '%s\n' "${s%% — *}"
  else
    printf '%s\n' "$s"
  fi
}

resolve_config() {
  local -a ifaces pci_opts module_opts conn_opts labels
  local pick i

  # Mode
  if [[ -z "$MODE" ]]; then
    MODE="$(prompt_choice "What do you want to do?" 1 \
      "recover — unfreeze / reconnect Wi-Fi (escalating)" \
      "status — show current Wi-Fi state" \
      "logs — show recent kernel Wi-Fi logs")"
    MODE="$(label_value "$MODE")"
  fi

  # Depth (recover only)
  if [[ "$MODE" == "recover" && -z "$QUICK" ]]; then
    pick="$(prompt_choice "How aggressive should recovery be?" 1 \
      "full — bounce → reload → PCI reset → remove/rescan" \
      "quick — bounce → module reload only")"
    if [[ "$(label_value "$pick")" == "quick" ]]; then
      QUICK=1
    else
      QUICK=0
    fi
  fi
  QUICK="${QUICK:-0}"

  # Interface
  if [[ -z "$IFACE" ]]; then
    mapfile -t ifaces < <(discover_ifaces)
    if [[ "${#ifaces[@]}" -eq 0 ]]; then
      if can_prompt; then
        read -r -p "No Wi-Fi interface detected. Enter interface name (e.g. wlp1s0): " IFACE
        [[ -n "$IFACE" ]] || die "Interface required"
      else
        die "No Wi-Fi interface found (set --iface or WIFI_IFACE)"
      fi
    else
      labels=()
      for i in "${ifaces[@]}"; do
        labels+=("$(iface_label "$i")")
      done
      pick="$(prompt_choice "Which Wi-Fi interface?" 1 "${labels[@]}")"
      IFACE="$(label_value "$pick")"
    fi
  fi

  # PCI device (needed for recover; useful for status)
  if [[ -z "$PCI_DEV" && "$MODE" == "recover" ]]; then
    mapfile -t pci_opts < <(discover_pci)
    if [[ "${#pci_opts[@]}" -eq 0 ]]; then
      if [[ -e "/sys/class/net/$IFACE/device" ]]; then
        PCI_DEV="$(basename "$(readlink -f "/sys/class/net/$IFACE/device")")"
        log "Derived PCI device from $IFACE: $PCI_DEV"
      elif can_prompt; then
        read -r -p "No wireless PCI device found. Enter PCI address (e.g. 0000:01:00.0), or leave empty to skip PCI steps: " PCI_DEV
      else
        PCI_DEV=""
        log "No PCI device found; PCI reset steps will be skipped"
      fi
    else
      pick="$(prompt_choice "Which wireless PCI device?" 1 "${pci_opts[@]}")"
      PCI_DEV="$(label_value "$pick")"
    fi
  elif [[ -z "$PCI_DEV" && -n "$IFACE" && -e "/sys/class/net/$IFACE/device" ]]; then
    PCI_DEV="$(basename "$(readlink -f "/sys/class/net/$IFACE/device")")"
  fi

  # Driver module
  if [[ -z "$MODULE" && "$MODE" == "recover" ]]; then
    mapfile -t module_opts < <({
      [[ -n "$PCI_DEV" ]] && discover_modules_for_pci "$PCI_DEV"
      discover_loaded_wifi_modules
    } | awk 'NF && !seen[$0]++')
    if [[ "${#module_opts[@]}" -eq 0 ]]; then
      if can_prompt; then
        read -r -p "Enter kernel module to reload (e.g. mt7921e): " MODULE
        [[ -n "$MODULE" ]] || die "Module required"
      else
        die "No Wi-Fi module found (set --module or WIFI_MODULE)"
      fi
    else
      MODULE="$(prompt_choice "Which kernel module should be reloaded?" 1 "${module_opts[@]}")"
    fi
  fi

  # NetworkManager connection (optional reconnect target)
  if [[ "$MODE" == "recover" && -z "$CONNECTION" ]] && nm_available; then
    mapfile -t conn_opts < <(discover_connections)
    if [[ "${#conn_opts[@]}" -eq 0 ]]; then
      CONNECTION=""
    elif [[ "${#conn_opts[@]}" -eq 1 ]]; then
      if ! can_prompt || prompt_confirm "Reconnect to saved network \"${conn_opts[0]}\" after fix?" y; then
        CONNECTION="${conn_opts[0]}"
      else
        CONNECTION=""
      fi
    else
      conn_opts+=("skip — don't auto-reconnect")
      pick="$(prompt_choice "Reconnect to which saved network after fix?" 1 "${conn_opts[@]}")"
      if [[ "$(label_value "$pick")" == "skip" ]]; then
        CONNECTION=""
      else
        CONNECTION="$pick"
      fi
    fi
  fi
}

# --- Actions --------------------------------------------------------------

show_status() {
  echo "=== Wi-Fi status ==="
  echo "iface=${IFACE:-?}  module=${MODULE:-?}  pci=${PCI_DEV:-?}"
  [[ -n "${CONNECTION:-}" ]] && echo "connection=$CONNECTION"
  echo
  rfkill list wifi 2>/dev/null || true
  echo
  if [[ -n "$IFACE" ]]; then
    ip -br link show "$IFACE" 2>/dev/null || echo "$IFACE: missing"
  else
    ip -br link
  fi
  echo
  if command -v iw >/dev/null 2>&1 && iface_exists; then
    iw dev "$IFACE" link 2>/dev/null || true
  fi
  echo
  if nm_available; then
    nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status 2>/dev/null | grep -E 'wifi|'"${IFACE:-^$}" || true
  fi
  if [[ -n "$MODULE" ]]; then
    lsmod | grep -E "^${MODULE}|^mt76|^iwl|^ath|^rtw" || echo "(module not loaded)"
  else
    discover_loaded_wifi_modules || echo "(no known wifi modules loaded)"
  fi
}

show_logs() {
  local pattern="firmware|80211|wlan"
  [[ -n "$IFACE" ]] && pattern="${pattern}|${IFACE}"
  [[ -n "$MODULE" ]] && pattern="${pattern}|${MODULE}"
  pattern="${pattern}|mt79|iwlwifi|ath1|rtw8"
  echo "=== Recent kernel Wi-Fi logs ==="
  journalctl -k -b --no-pager 2>/dev/null \
    | grep -iE "$pattern" \
    | tail -60 \
    || dmesg -T 2>/dev/null | grep -iE "$pattern" | tail -60 \
    || true
}

unblock_wifi() {
  log "Step 1/5: unblock rfkill + enable radio"
  command -v rfkill >/dev/null 2>&1 && rfkill unblock wifi || true
  if nm_available; then
    nmcli radio wifi on 2>/dev/null || true
  fi
}

bounce_iface() {
  log "Step 2/5: bounce interface $IFACE"
  iface_exists || {
    log "Interface $IFACE not present yet (will continue)"
    return 0
  }
  ip link set "$IFACE" down || true
  sleep 1
  ip link set "$IFACE" up || true
}

reload_module() {
  log "Step 3/5: reload module $MODULE"
  if nm_available; then
    nmcli radio wifi off 2>/dev/null || true
  fi
  if iface_exists; then
    ip link set "$IFACE" down 2>/dev/null || true
  fi
  modprobe -r "$MODULE" 2>/dev/null || {
    log "Soft unload failed; continuing (PCI steps may still help)"
    true
  }
  sleep 1
  modprobe "$MODULE" || die "Failed to load $MODULE"
  sleep 2
  if nm_available; then
    nmcli radio wifi on 2>/dev/null || true
  fi
  if wait_for 8 iface_exists; then
    ip link set "$IFACE" up 2>/dev/null || true
  else
    log "Interface $IFACE did not reappear after module reload"
  fi
}

pci_reset() {
  log "Step 4/5: PCI reset $PCI_DEV"
  [[ -n "$PCI_DEV" ]] || {
    log "No PCI device configured; skipping reset"
    return 0
  }
  pci_exists || {
    log "PCI device $PCI_DEV missing; skipping reset"
    return 0
  }
  if [[ ! -f "/sys/bus/pci/devices/$PCI_DEV/reset" ]]; then
    log "No reset attribute; skipping"
    return 0
  fi
  if nm_available; then
    nmcli radio wifi off 2>/dev/null || true
  fi
  modprobe -r "$MODULE" 2>/dev/null || true
  sleep 1
  echo 1 > "/sys/bus/pci/devices/$PCI_DEV/reset"
  sleep 2
  modprobe "$MODULE" || die "Failed to load $MODULE after PCI reset"
  sleep 2
  if nm_available; then
    nmcli radio wifi on 2>/dev/null || true
  fi
  wait_for 10 iface_exists && ip link set "$IFACE" up 2>/dev/null || true
}

pci_remove_rescan() {
  log "Step 5/5: PCI remove + rescan $PCI_DEV"
  [[ -n "$PCI_DEV" ]] || {
    log "No PCI device configured; skipping remove/rescan"
    return 0
  }
  if nm_available; then
    nmcli radio wifi off 2>/dev/null || true
  fi
  modprobe -r "$MODULE" 2>/dev/null || true
  sleep 1
  if pci_exists; then
    echo 1 > "/sys/bus/pci/devices/$PCI_DEV/remove"
    sleep 2
  else
    log "Device already gone; rescanning anyway"
  fi
  echo 1 > /sys/bus/pci/rescan
  sleep 2
  wait_for 10 pci_exists || die "PCI device $PCI_DEV did not return after rescan"
  modprobe "$MODULE" || die "Failed to load $MODULE after rescan"
  sleep 2
  if nm_available; then
    nmcli radio wifi on 2>/dev/null || true
  fi
  wait_for 10 iface_exists && ip link set "$IFACE" up 2>/dev/null || true
}

disable_powersave() {
  if command -v iw >/dev/null 2>&1 && iface_exists; then
    iw dev "$IFACE" set power_save off 2>/dev/null || true
  fi
  if command -v iwconfig >/dev/null 2>&1 && iface_exists; then
    iwconfig "$IFACE" power off 2>/dev/null || true
  fi
}

try_reconnect() {
  nm_available || return 0
  [[ -n "${CONNECTION:-}" ]] || return 0
  log "Attempting NetworkManager reconnect: $CONNECTION"
  nmcli connection up "$CONNECTION" ifname "$IFACE" 2>/dev/null || true
}

recovery_ok() {
  iface_exists || return 1
  local soft
  soft="$(rfkill list wifi 2>/dev/null | awk '/Soft blocked/{print $3; exit}')"
  [[ "${soft:-no}" == "no" ]] || return 1
  ip link show "$IFACE" 2>/dev/null | grep -q 'UP' || return 1
  return 0
}

recover() {
  need_root
  log "Starting Wi-Fi fix (iface=$IFACE module=$MODULE pci=${PCI_DEV:-none} quick=$QUICK)"
  show_logs | logger -t "$LOG_TAG" 2>/dev/null || true

  unblock_wifi
  bounce_iface
  disable_powersave
  if recovery_ok && wifi_associated; then
    log "Recovered after interface bounce"
    show_status
    exit 0
  fi

  reload_module
  disable_powersave
  try_reconnect
  if recovery_ok; then
    log "Recovered after module reload"
    show_status
    exit 0
  fi

  if [[ "$QUICK" -eq 1 ]]; then
    log "Quick mode: stopping before PCI reset"
    show_status
    exit 1
  fi

  if [[ -n "$PCI_DEV" ]] && can_prompt; then
    prompt_confirm "Module reload wasn't enough. Continue with PCI reset?" y || {
      log "Stopped before PCI reset (user choice)"
      show_status
      exit 1
    }
  fi

  pci_reset
  disable_powersave
  try_reconnect
  if recovery_ok; then
    log "Recovered after PCI reset"
    show_status
    exit 0
  fi

  if [[ -n "$PCI_DEV" ]] && can_prompt; then
    prompt_confirm "PCI reset wasn't enough. Continue with remove + rescan?" y || {
      log "Stopped before PCI remove/rescan (user choice)"
      show_status
      exit 1
    }
  fi

  pci_remove_rescan
  disable_powersave
  try_reconnect
  if recovery_ok; then
    log "Recovered after PCI remove/rescan"
    show_status
    exit 0
  fi

  log "Fix finished but Wi-Fi still looks unhealthy"
  show_status
  echo
  show_logs
  exit 1
}

# --- CLI ------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    -y|--yes) ASSUME_YES=1 ;;
    --quick) QUICK=1; MODE="${MODE:-recover}" ;;
    --full) QUICK=0; MODE="${MODE:-recover}" ;;
    --status) MODE="status" ;;
    --logs) MODE="logs" ;;
    --recover) MODE="recover" ;;
    --iface) IFACE="${2:?}"; shift ;;
    --pci) PCI_DEV="${2:?}"; shift ;;
    --module) MODULE="${2:?}"; shift ;;
    --connection|--conn) CONNECTION="${2:?}"; shift ;;
    *) die "Unknown option: $1 (see --help)" ;;
  esac
  shift
done

# --yes with no mode → recover
if [[ "$ASSUME_YES" -eq 1 && -z "$MODE" ]]; then
  MODE="recover"
  QUICK="${QUICK:-0}"
fi

resolve_config

case "$MODE" in
  status) show_status ;;
  logs) show_logs ;;
  recover) recover ;;
  *) die "Unknown mode: $MODE" ;;
esac
