# dl

Download direct image URLs over HTTP, or forward everything else to [yt-dlp](https://github.com/yt-dlp/yt-dlp). Intended as a drop-in replacement for a `dl` → `yt-dlp` symlink.

## Build

```powershell
go build -o dl.exe .
```

Put `dl.exe` (or `dl` on Unix) on your PATH where the old symlink lived.

## Usage

```
dl [options] <url> [url...]
dl [yt-dlp-options] <url>
```

- **Images** — URL path ends with an image extension, or the response `Content-Type` is `image/*` (including avif, jxl, webp, gif, …). Saved to the current directory by default.
- **Everything else** — Arguments are forwarded unchanged to `yt-dlp`.

## Options

| Flag | Description |
|------|-------------|
| `--yt-dlp PATH` | yt-dlp binary (default: `yt-dlp`, or env `DL_YT_DLP`) |
| `--dl-help` | Show wrapper help |
| `-o`, `--output PATH` | Image mode only: output file (one URL) or directory |
| `-q`, `--quiet` | Image mode only: suppress progress on stderr (saved path still on stdout) |

`-o` / `-q` are only consumed when at least one URL is classified as an image; otherwise they are passed through to yt-dlp.

## Supported image extensions

`jpg`, `jpeg`, `jfif`, `png`, `gif`, `webp`, `avif`, `jxl`, `bmp`, `tif`, `tiff`, `heic`, `heif`, `ico`, `svg`, `jp2`

## Examples

```powershell
dl https://example.com/photo.avif
dl -o out.webp https://cdn.example/signed-image
dl -f bv+ba https://www.youtube.com/watch?v=dQw4w9WgXcQ
dl --yt-dlp C:\Tools\yt-dlp.exe https://youtu.be/dQw4w9WgXcQ
```
