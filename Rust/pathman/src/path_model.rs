//! Split/join PATH strings, normalize, dedupe.

#[cfg(windows)]
const SEP: char = ';';
#[cfg(not(windows))]
const SEP: char = ':';

/// Split a PATH string into non-empty entries (trimmed).
pub fn split(raw: &str) -> Vec<String> {
    raw.split(SEP)
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

/// Join entries with the platform separator. Skips empty strings.
pub fn join(entries: &[String]) -> String {
    entries
        .iter()
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect::<Vec<_>>()
        .join(&SEP.to_string())
}

/// Remove consecutive duplicate entries and empty entries.
pub fn dedupe_adjacent(entries: &[String]) -> Vec<String> {
    let mut out = Vec::new();
    for e in entries {
        let t = e.trim();
        if t.is_empty() {
            continue;
        }
        if out.last().map(|l: &String| l.as_str()) == Some(t) {
            continue;
        }
        out.push(t.to_string());
    }
    out
}

/// True if the path exists and is a directory (or on Windows, exists as file — drive roots).
pub fn entry_exists(path: &str) -> bool {
    let p = std::path::Path::new(path);
    if p.is_dir() {
        return true;
    }
    #[cfg(windows)]
    {
        // Drive root "C:\" may report not dir in edge cases; accept existing prefix
        if path.len() == 3 && path.ends_with(":\\") {
            return p.exists();
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn split_join_roundtrip() {
        #[cfg(windows)]
        let s = r"C:\a;C:\b;C:\c";
        #[cfg(not(windows))]
        let s = "/a:/b:/c";
        let v = split(s);
        assert!(!v.is_empty());
        let j = join(&v);
        assert_eq!(split(&j), v);
    }

    #[test]
    fn dedupe() {
        let v = vec![
            "/a".into(),
            "/a".into(),
            "".into(),
            "/b".into(),
        ];
        assert_eq!(dedupe_adjacent(&v), vec!["/a", "/b"]);
    }
}
