param(
  [Parameter(Mandatory=$true)][string]$Url,
  [string]$Dl = "yt-dlp"
)

function Test-VideoDecode([string]$path) {
  & ffmpeg -hide_banner -v error -stats -i $path -map 0:v:0 -f null - 2>&1 | Out-Null
  return $LASTEXITCODE -eq 0
}

$attempts = @(
  @{ Args = @("--force-overwrites", "-f", "1080p", $Url) },
  @{ Args = @("--force-overwrites", "-f", "720p",  $Url) },
  @{ Args = @("--force-overwrites", "-f", "480p",  $Url) }
)

foreach ($a in $attempts) {
  & $Dl @($a.Args)
  if ($LASTEXITCODE -ne 0) { continue }

  # Find newest mp4 in cwd (simple heuristic) — better: parse yt-dlp --print filename
  $f = Get-ChildItem -File -Filter *.mp4 | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $f) { continue }

  if (Test-VideoDecode $f.FullName) { exit 0 }

  Remove-Item -LiteralPath $f.FullName -Force
}

throw "Download/verify failed for all fallbacks."