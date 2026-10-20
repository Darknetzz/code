use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use base64::{engine::general_purpose::STANDARD, Engine as _};
use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(
    name = "imgb64",
    about = "Encode/decode images as data URIs or raw base64",
    version
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Encode an image to a data URI (default) or raw base64
    Encode {
        /// Input image path, or `-` for stdin
        input: PathBuf,
        /// Output path, or `-` for stdout (default: stdout)
        #[arg(short, long)]
        output: Option<PathBuf>,
        /// Emit raw base64 only (no data: prefix)
        #[arg(long)]
        raw: bool,
    },
    /// Decode a data URI or raw base64 back to image bytes
    Decode {
        /// Input text path, or `-` for stdin
        input: PathBuf,
        /// Output image path, or `-` for stdout (default: stdout)
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Encode {
            input,
            output,
            raw,
        } => cmd_encode(&input, output.as_deref(), raw),
        Commands::Decode { input, output } => cmd_decode(&input, output.as_deref()),
    }
}

fn cmd_encode(input: &Path, output: Option<&Path>, raw: bool) -> Result<()> {
    let bytes = read_bytes(input)?;
    let mime = mime_from_path(input)
        .or_else(|| mime_from_bytes(&bytes))
        .unwrap_or("application/octet-stream");
    let encoded = encode_bytes(&bytes);
    let text = if raw {
        encoded
    } else {
        to_data_uri(mime, &encoded)
    };
    write_text(output, &text)?;
    Ok(())
}

fn cmd_decode(input: &Path, output: Option<&Path>) -> Result<()> {
    let text = read_text(input)?;
    let (mime, payload) = strip_data_uri(&text);
    let bytes = decode_text(payload).context("invalid base64")?;
    let out = resolve_decode_output(output, mime);
    write_bytes(out.as_deref(), &bytes)?;
    Ok(())
}

fn read_bytes(path: &Path) -> Result<Vec<u8>> {
    if is_stdio(path) {
        let mut buf = Vec::new();
        io::stdin()
            .read_to_end(&mut buf)
            .context("failed to read stdin")?;
        Ok(buf)
    } else {
        fs::read(path).with_context(|| format!("failed to read {}", path.display()))
    }
}

fn read_text(path: &Path) -> Result<String> {
    if is_stdio(path) {
        let mut buf = String::new();
        io::stdin()
            .read_to_string(&mut buf)
            .context("failed to read stdin")?;
        Ok(buf)
    } else {
        fs::read_to_string(path).with_context(|| format!("failed to read {}", path.display()))
    }
}

fn write_text(path: Option<&Path>, text: &str) -> Result<()> {
    if use_stdout(path) {
        let mut out = io::stdout().lock();
        out.write_all(text.as_bytes())
            .context("failed to write stdout")?;
        if !text.ends_with('\n') {
            out.write_all(b"\n").context("failed to write stdout")?;
        }
        return Ok(());
    }
    let path = path.expect("checked by use_stdout");
    fs::write(path, text.as_bytes()).with_context(|| format!("failed to write {}", path.display()))
}

fn write_bytes(path: Option<&Path>, bytes: &[u8]) -> Result<()> {
    if use_stdout(path) {
        io::stdout()
            .write_all(bytes)
            .context("failed to write stdout")?;
        return Ok(());
    }
    let path = path.expect("checked by use_stdout");
    fs::write(path, bytes).with_context(|| format!("failed to write {}", path.display()))
}

fn use_stdout(path: Option<&Path>) -> bool {
    match path {
        None => true,
        Some(p) => is_stdio(p),
    }
}

fn is_stdio(path: &Path) -> bool {
    path.as_os_str() == "-"
}

fn encode_bytes(bytes: &[u8]) -> String {
    STANDARD.encode(bytes)
}

fn decode_text(text: &str) -> Result<Vec<u8>> {
    let cleaned: String = text.chars().filter(|c| !c.is_whitespace()).collect();
    if cleaned.is_empty() {
        bail!("empty base64 input");
    }
    STANDARD
        .decode(cleaned.as_bytes())
        .context("base64 decode failed")
}

fn to_data_uri(mime: &str, b64: &str) -> String {
    format!("data:{mime};base64,{b64}")
}

/// Returns (optional MIME from data URI, base64 payload).
fn strip_data_uri(text: &str) -> (Option<&str>, &str) {
    let trimmed = text.trim();
    let Some(rest) = trimmed.strip_prefix("data:") else {
        return (None, trimmed);
    };
    let Some((meta, payload)) = rest.split_once(',') else {
        return (None, trimmed);
    };
    let mime = meta
        .split(';')
        .next()
        .map(str::trim)
        .filter(|m| !m.is_empty());
    (mime, payload.trim())
}

fn mime_from_path(path: &Path) -> Option<&'static str> {
    let ext = path.extension()?.to_str()?.to_ascii_lowercase();
    Some(match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "svg" => "image/svg+xml",
        "ico" => "image/x-icon",
        _ => return None,
    })
}

fn mime_from_bytes(bytes: &[u8]) -> Option<&'static str> {
    if bytes.starts_with(&[0x89, b'P', b'N', b'G', b'\r', b'\n', 0x1a, b'\n']) {
        return Some("image/png");
    }
    if bytes.starts_with(&[0xff, 0xd8, 0xff]) {
        return Some("image/jpeg");
    }
    if bytes.starts_with(b"GIF87a") || bytes.starts_with(b"GIF89a") {
        return Some("image/gif");
    }
    if bytes.len() >= 12 && &bytes[0..4] == b"RIFF" && &bytes[8..12] == b"WEBP" {
        return Some("image/webp");
    }
    if bytes.starts_with(b"BM") {
        return Some("image/bmp");
    }
    None
}

fn ext_from_mime(mime: &str) -> Option<&'static str> {
    Some(match mime {
        "image/png" => "png",
        "image/jpeg" => "jpg",
        "image/gif" => "gif",
        "image/webp" => "webp",
        "image/bmp" => "bmp",
        "image/svg+xml" => "svg",
        "image/x-icon" | "image/vnd.microsoft.icon" => "ico",
        _ => return None,
    })
}

/// If `-o` is a path without an extension and MIME is known, append a default extension.
fn resolve_decode_output(output: Option<&Path>, mime: Option<&str>) -> Option<PathBuf> {
    let Some(path) = output else {
        return None;
    };
    if is_stdio(path) {
        return Some(path.to_path_buf());
    }
    if path.extension().is_some() {
        return Some(path.to_path_buf());
    }
    if let Some(mime) = mime {
        if let Some(ext) = ext_from_mime(mime) {
            let mut with_ext = path.to_path_buf();
            with_ext.set_extension(ext);
            return Some(with_ext);
        }
    }
    Some(path.to_path_buf())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_data_uri() {
        let png = b"\x89PNG\r\n\x1a\nfake";
        let b64 = encode_bytes(png);
        let uri = to_data_uri("image/png", &b64);
        let (mime, payload) = strip_data_uri(&uri);
        assert_eq!(mime, Some("image/png"));
        assert_eq!(decode_text(payload).unwrap(), png);
    }

    #[test]
    fn strip_raw_base64() {
        let (mime, payload) = strip_data_uri(" aGVsbG8= \n");
        assert_eq!(mime, None);
        assert_eq!(decode_text(payload).unwrap(), b"hello");
    }

    #[test]
    fn sniff_png() {
        assert_eq!(
            mime_from_bytes(b"\x89PNG\r\n\x1a\n"),
            Some("image/png")
        );
    }
}
