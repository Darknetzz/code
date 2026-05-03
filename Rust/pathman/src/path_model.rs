//! Split/join PATH strings, normalize, dedupe.

#[cfg(windows)]
const SEP: char = ';';
#[cfg(not(windows))]
const SEP: char = ':';

/// Whether a merged PATH segment came from the machine (system) store or the user store.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PathOrigin {
    Machine,
    User,
}

/// Machine entries, then user, then adjacent dedupe of strings (same ordering as the Effective tab).
pub fn merge_machine_user_preview_style(
    machine: &[String],
    user: &[String],
) -> Vec<(PathOrigin, String)> {
    let mut v: Vec<(PathOrigin, String)> = machine
        .iter()
        .map(|s| (PathOrigin::Machine, s.trim().to_string()))
        .filter(|(_, s)| !s.is_empty())
        .chain(
            user
                .iter()
                .map(|s| (PathOrigin::User, s.trim().to_string()))
                .filter(|(_, s)| !s.is_empty()),
        )
        .collect();
    dedupe_adjacent_tagged(&mut v);
    v
}

/// Remove adjacent duplicate *paths* (string equality), keeping the first segment’s origin.
pub fn dedupe_adjacent_tagged(v: &mut Vec<(PathOrigin, String)>) {
    let mut i = 1;
    while i < v.len() {
        if v[i].1 == v[i - 1].1 {
            v.remove(i);
        } else {
            i += 1;
        }
    }
}

/// Split back into machine and user entry lists (order preserved within each).
pub fn split_origins(segments: &[(PathOrigin, String)]) -> (Vec<String>, Vec<String>) {
    let mut m = Vec::new();
    let mut u = Vec::new();
    for (o, s) in segments {
        let t = s.trim();
        if t.is_empty() {
            continue;
        }
        match o {
            PathOrigin::Machine => m.push(t.to_string()),
            PathOrigin::User => u.push(t.to_string()),
        }
    }
    (m, u)
}

/// Build the merged PATH string from machine + user lists (used in tests; mirrors Effective-tab join).
#[cfg(test)]
pub fn join_merged_preview_style(machine: &[String], user: &[String]) -> String {
    let v = merge_machine_user_preview_style(machine, user);
    let flat: Vec<String> = v.iter().map(|(_, s)| s.clone()).collect();
    join(&flat)
}

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

/// Expand `%VAR%` (Windows) or shell-style segments (Unix) for checks and display.
pub fn expanded_path(raw: &str) -> String {
    #[cfg(windows)]
    {
        expand_windows(raw)
    }
    #[cfg(not(windows))]
    {
        shellexpand::full(raw)
            .map(|c| c.into_owned())
            .unwrap_or_else(|_| raw.to_string())
    }
}

#[cfg(windows)]
fn expand_windows(raw: &str) -> String {
    use std::ffi::OsString;
    use std::os::windows::ffi::OsStringExt;
    use windows_sys::Win32::System::Environment::ExpandEnvironmentStringsW;

    let mut wide: Vec<u16> = raw.encode_utf16().collect();
    wide.push(0);

    let needed = unsafe { ExpandEnvironmentStringsW(wide.as_ptr(), std::ptr::null_mut(), 0) };
    if needed == 0 {
        return raw.to_string();
    }
    let mut out = vec![0u16; needed as usize];
    let n = unsafe { ExpandEnvironmentStringsW(wide.as_ptr(), out.as_mut_ptr(), needed) };
    if n == 0 {
        return raw.to_string();
    }
    while out.last().copied() == Some(0) {
        out.pop();
    }
    OsString::from_wide(&out).to_string_lossy().into_owned()
}

/// True if the path exists and is a directory (or on Windows, exists as file — drive roots).
/// Uses [`expanded_path`] so `%ProgramFiles%\Foo` resolves before checking.
pub fn entry_exists(raw: &str) -> bool {
    let path = expanded_path(raw);
    let p = std::path::Path::new(path.as_str());
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

    #[test]
    fn merge_preview_matches_flat_dedupe() {
        let machine = vec!["a".into(), "b".into()];
        let user = vec!["b".into(), "c".into()];
        let merged_tagged = merge_machine_user_preview_style(&machine, &user);
        assert_eq!(
            merged_tagged,
            vec![
                (PathOrigin::Machine, "a".into()),
                (PathOrigin::Machine, "b".into()),
                (PathOrigin::User, "c".into()),
            ]
        );
        let flat: Vec<String> = merged_tagged.iter().map(|(_, s)| s.clone()).collect();
        let mut naive = machine.clone();
        naive.extend(user.clone());
        assert_eq!(flat, dedupe_adjacent(&naive));

        let (m2, u2) = split_origins(&merged_tagged);
        let again = join_merged_preview_style(&m2, &u2);
        assert_eq!(again, join(&flat));
    }

    #[test]
    fn split_roundtrip_tagged() {
        let m = vec!["C:\\M1".into()];
        let u = vec!["C:\\U1".into(), "C:\\U2".into()];
        let seg = merge_machine_user_preview_style(&m, &u);
        let (m2, u2) = split_origins(&seg);
        assert_eq!(m2, m);
        assert_eq!(u2, u);
    }
}
