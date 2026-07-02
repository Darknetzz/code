//! Tab-completion logic for the interactive REPL.

use std::collections::HashSet;
use std::path::{Path, PathBuf};

use rustyline::completion::Pair;

use crate::builtins::BUILTIN_NAMES;
use crate::shell::{home_dir, ShellState};

#[derive(Debug, Clone, PartialEq, Eq)]
struct CompletionParse {
    words: Vec<String>,
    current_start: usize,
    current: String,
    in_double_quotes: bool,
    word_index: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CompletionMode {
    Command,
    Path { dirs_only: bool },
    EnvVar,
    Builtin,
    CommandName,
}

/// Returns `(word_start, candidates)` for rustyline.
pub fn completions_at(st: &ShellState, line: &str, pos: usize) -> (usize, Vec<Pair>) {
    let parse = parse_for_completion(line, pos);
    if parse.current.is_empty() {
        return (parse.current_start, Vec::new());
    }

    let (word_start, word) = env_var_word(&parse);
    let first_word = parse.words.first().map(String::as_str);
    let mode = completion_mode(word, parse.word_index, first_word);

    let mut candidates = match mode {
        CompletionMode::Command => complete_commands(st, word),
        CompletionMode::Path { dirs_only } => {
            let mut paths = complete_paths(st, word, dirs_only);
            if dirs_only {
                paths.extend(complete_cd_special(st, word));
            }
            paths
        }
        CompletionMode::EnvVar => complete_env_vars(st, word, word_start, &parse),
        CompletionMode::Builtin => complete_builtins(word),
        CompletionMode::CommandName => complete_command_names(st, word),
    };

    candidates.sort_by(|a, b| a.display.cmp(&b.display));
    candidates.dedup_by(|a, b| a.replacement == b.replacement);
    (word_start, candidates)
}

/// Quote-aware tokenizer up to `pos` for completion context.
fn parse_for_completion(line: &str, pos: usize) -> CompletionParse {
    let pos = pos.min(line.len());
    let mut words = Vec::new();
    let mut current = String::new();
    let mut current_start = 0;
    let mut in_double_quotes = false;
    let mut i = 0;

    while i < pos {
        let ch = line[i..].chars().next().unwrap();
        let ch_len = ch.len_utf8();

        if in_double_quotes {
            if ch == '\\' && i + ch_len < pos {
                let next = line[i + ch_len..].chars().next().unwrap();
                current.push(next);
                i += ch_len + next.len_utf8();
                continue;
            }
            if ch == '"' {
                in_double_quotes = false;
                i += ch_len;
                continue;
            }
            if current.is_empty() {
                current_start = i;
            }
            current.push(ch);
            i += ch_len;
            continue;
        }

        if ch.is_whitespace() {
            if !current.is_empty() {
                words.push(std::mem::take(&mut current));
            }
            i += ch_len;
            while i < pos {
                let ws = line[i..].chars().next().unwrap();
                if !ws.is_whitespace() {
                    break;
                }
                i += ws.len_utf8();
            }
            current_start = i;
            continue;
        }

        if ch == '"' {
            in_double_quotes = true;
            i += ch_len;
            if current.is_empty() {
                current_start = i;
            }
            continue;
        }

        if current.is_empty() {
            current_start = i;
        }
        current.push(ch);
        i += ch_len;
    }

    let word_index = words.len();
    CompletionParse {
        words,
        current_start,
        current,
        in_double_quotes,
        word_index,
    }
}

fn env_var_word(parse: &CompletionParse) -> (usize, &str) {
    if let Some(dollar) = parse.current.rfind('$') {
        (parse.current_start + dollar, &parse.current[dollar..])
    } else {
        (parse.current_start, &parse.current)
    }
}

fn completion_mode(word: &str, word_index: usize, first_word: Option<&str>) -> CompletionMode {
    if word.starts_with('$') || word.contains('$') {
        return CompletionMode::EnvVar;
    }

    if word_index == 0 {
        return CompletionMode::Command;
    }

    match first_word {
        Some("cd") => CompletionMode::Path { dirs_only: true },
        Some("source") | Some(".") => CompletionMode::Path { dirs_only: false },
        Some("help") => CompletionMode::Builtin,
        Some("export") | Some("unset") => CompletionMode::EnvVar,
        Some("type") => CompletionMode::CommandName,
        _ => CompletionMode::Path { dirs_only: false },
    }
}

fn complete_commands(st: &ShellState, word: &str) -> Vec<Pair> {
    let mut candidates = complete_builtins(word);
    candidates.extend(complete_functions(st, word));
    candidates.extend(complete_path_executables(st, word));
    if !word.contains(std::path::MAIN_SEPARATOR) && !word.contains('/') && !word.contains('\\') {
        candidates.extend(complete_paths(st, word, false));
    }
    candidates
}

fn complete_command_names(st: &ShellState, word: &str) -> Vec<Pair> {
    let mut candidates = complete_builtins(word);
    candidates.extend(complete_functions(st, word));
    candidates.extend(complete_path_executables(st, word));
    candidates
}

fn complete_cd_special(st: &ShellState, word: &str) -> Vec<Pair> {
    if st.prev_cwd.is_some() && "-".starts_with(word) {
        vec![pair("-", "-")]
    } else {
        Vec::new()
    }
}

fn complete_builtins(word: &str) -> Vec<Pair> {
    BUILTIN_NAMES
        .iter()
        .filter(|name| name.starts_with(word))
        .map(|name| pair(*name, *name))
        .collect()
}

fn complete_functions(st: &ShellState, word: &str) -> Vec<Pair> {
    let mut fnames: Vec<_> = st.functions.keys().map(String::as_str).collect();
    fnames.sort();
    fnames
        .into_iter()
        .filter(|name| name.starts_with(word))
        .map(|name| pair(name, name))
        .collect()
}

fn complete_env_vars(
    st: &ShellState,
    word: &str,
    word_start: usize,
    parse: &CompletionParse,
) -> Vec<Pair> {
    let (var_prefix, with_dollar) = if let Some(rest) = word.strip_prefix('$') {
        (rest, true)
    } else {
        (word, false)
    };

    let prefix_in_word = word_start.saturating_sub(parse.current_start);

    let mut keys: Vec<_> = st.env.keys().map(String::as_str).collect();
    keys.sort();
    keys.into_iter()
        .filter(|key| key.starts_with(var_prefix))
        .map(|key| {
            if with_dollar {
                let replacement = format!("${key}");
                if parse.in_double_quotes {
                    let before = &parse.current[..prefix_in_word];
                    pair(
                        format!("{before}{replacement}"),
                        format!("{before}{replacement}"),
                    )
                } else {
                    pair(replacement.clone(), replacement)
                }
            } else {
                pair(key, key)
            }
        })
        .collect()
}

fn prefix_matches(name: &str, prefix: &str) -> bool {
    if prefix.is_empty() {
        return true;
    }
    if cfg!(windows) {
        name.len() >= prefix.len() && name[..prefix.len()].eq_ignore_ascii_case(prefix)
    } else {
        name.starts_with(prefix)
    }
}

/// Directory entries, including Windows junctions/reparse points (e.g. `Documents`).
fn is_directory_entry(path: &Path) -> bool {
    let Ok(meta) = std::fs::symlink_metadata(path) else {
        return false;
    };
    if meta.is_dir() {
        return true;
    }
    if meta.is_symlink() {
        return std::fs::metadata(path).map(|m| m.is_dir()).unwrap_or(false);
    }
    false
}

fn complete_paths(st: &ShellState, word: &str, dirs_only: bool) -> Vec<Pair> {
    let (dir, base_prefix) = path_completion_parts(&st.cwd, word);
    let Ok(entries) = std::fs::read_dir(&dir) else {
        return Vec::new();
    };

    let mut candidates = Vec::new();
    for entry in entries.flatten() {
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with('.') && !base_prefix.starts_with('.') {
            continue;
        }
        if !prefix_matches(&name, &base_prefix) {
            continue;
        }

        let path = entry.path();
        let is_dir = is_directory_entry(&path);
        if dirs_only && !is_dir {
            continue;
        }

        let mut replacement = path_replacement(word, &name);
        if is_dir {
            replacement.push(std::path::MAIN_SEPARATOR);
        }
        candidates.push(pair(name, replacement));
    }
    candidates
}

fn complete_path_executables(st: &ShellState, word: &str) -> Vec<Pair> {
    if word.is_empty()
        || word.contains(std::path::MAIN_SEPARATOR)
        || word.contains('/')
        || word.contains('\\')
    {
        return Vec::new();
    }

    let path_var = st
        .get_var("PATH")
        .or_else(|| std::env::var("PATH").ok())
        .unwrap_or_default();
    let sep = if cfg!(windows) { ';' } else { ':' };
    let mut seen = HashSet::new();
    let mut candidates = Vec::new();

    for dir in path_var.split(sep) {
        let dir = dir.trim();
        if dir.is_empty() {
            continue;
        }
        let Ok(entries) = std::fs::read_dir(dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            if !is_path_executable(&path) {
                continue;
            }
            let Some(cmd_name) = executable_command_name(&path) else {
                continue;
            };
            if !prefix_matches(&cmd_name, word) || !seen.insert(cmd_name.clone()) {
                continue;
            }
            candidates.push(pair(cmd_name.clone(), cmd_name));
        }
    }

    candidates
}

fn is_path_executable(path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        path.metadata()
            .map(|m| m.permissions().mode() & 0o111 != 0)
            .unwrap_or(false)
    }
    #[cfg(windows)]
    {
        let _ = path;
        true
    }
}

fn executable_command_name(path: &Path) -> Option<String> {
    let file_name = path.file_name()?.to_string_lossy();
    #[cfg(windows)]
    {
        let lower = file_name.to_ascii_lowercase();
        const EXTS: &[&str] = &[".exe", ".cmd", ".bat", ".com"];
        if !EXTS.iter().any(|ext| lower.ends_with(ext)) {
            return None;
        }
        Some(
            Path::new(file_name.as_ref())
                .file_stem()?
                .to_string_lossy()
                .into_owned(),
        )
    }
    #[cfg(not(windows))]
    {
        Some(file_name.into_owned())
    }
}

fn path_completion_parts(cwd: &Path, word: &str) -> (PathBuf, String) {
    if let Some(rest) = word.strip_prefix('~') {
        let home = home_dir();
        let rest = rest.strip_prefix(['/', '\\']).unwrap_or(rest);
        return split_dir_and_prefix(&home, rest);
    }

    let path = Path::new(word);
    if path.is_absolute() {
        return split_dir_and_prefix(
            path.parent().unwrap_or(Path::new("/")),
            path.file_name()
                .and_then(|s| s.to_str())
                .unwrap_or(word),
        );
    }

    if word.contains('\\') || word.contains('/') {
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .map(|p| cwd.join(p))
            .unwrap_or_else(|| cwd.to_path_buf());
        split_dir_and_prefix(
            parent.as_path(),
            path.file_name()
                .and_then(|s| s.to_str())
                .unwrap_or(word),
        )
    } else {
        (cwd.to_path_buf(), word.to_string())
    }
}

fn split_dir_and_prefix(base: &Path, rest: &str) -> (PathBuf, String) {
    if rest.contains('\\') || rest.contains('/') {
        let path = Path::new(rest);
        let parent = path
            .parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or_else(|| Path::new("."));
        let prefix = path
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or(rest)
            .to_string();
        (base.join(parent), prefix)
    } else {
        (base.to_path_buf(), rest.to_string())
    }
}

fn path_replacement(word: &str, entry_name: &str) -> String {
    if word.starts_with('~') {
        let rest = word
            .strip_prefix('~')
            .unwrap_or(word)
            .strip_prefix(['/', '\\'])
            .unwrap_or("");
        if rest.is_empty() {
            return format!("~{sep}{entry_name}", sep = std::path::MAIN_SEPARATOR);
        }
        if rest.contains('/') || rest.contains('\\') {
            let parent = Path::new(rest).parent().unwrap_or(Path::new(""));
            if parent.as_os_str().is_empty() {
                return format!("~{sep}{entry_name}", sep = std::path::MAIN_SEPARATOR);
            }
            return format!(
                "~{sep}{}{sep}{entry_name}",
                parent.display(),
                sep = std::path::MAIN_SEPARATOR
            );
        }
        return format!("~{sep}{entry_name}", sep = std::path::MAIN_SEPARATOR);
    }

    if Path::new(word).is_absolute() {
        let parent = Path::new(word).parent().unwrap_or(Path::new("/"));
        return parent.join(entry_name).to_string_lossy().into_owned();
    }

    if word.contains('\\') || word.contains('/') {
        let parent = Path::new(word).parent().unwrap_or(Path::new("."));
        return parent.join(entry_name).to_string_lossy().into_owned();
    }

    entry_name.to_string()
}

fn pair(display: impl Into<String>, replacement: impl Into<String>) -> Pair {
    Pair {
        display: display.into(),
        replacement: replacement.into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::sync::atomic::{AtomicU64, Ordering};

    static TEMP_COUNTER: AtomicU64 = AtomicU64::new(0);

    fn test_state(cwd: PathBuf) -> ShellState {
        let mut st = ShellState::minimal();
        st.cwd = cwd;
        st.env.insert("HOME".into(), "/home/user".into());
        st.env.insert("PATH".into(), "/bin".into());
        st.functions.insert("myfn".into(), Vec::new());
        st
    }

    fn temp_dir_with(entries: &[&str]) -> PathBuf {
        let n = TEMP_COUNTER.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!("dsh-complete-{n}"));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        for entry in entries {
            let is_dir = entry.ends_with('/');
            let name = entry.trim_end_matches('/');
            let path = dir.join(name);
            if is_dir {
                fs::create_dir_all(&path).unwrap();
            } else {
                fs::write(&path, "").unwrap();
            }
        }
        dir
    }

    fn replacements(st: &ShellState, line: &str, pos: usize) -> Vec<String> {
        completions_at(st, line, pos)
            .1
            .into_iter()
            .map(|p| p.replacement)
            .collect()
    }

    #[test]
    fn completes_first_word_builtins() {
        let st = test_state(PathBuf::from("."));
        let reps = replacements(&st, "ec", 2);
        assert!(reps.iter().any(|r| r == "echo"));
    }

    #[test]
    fn completes_cd_directory_argument() {
        let dir = temp_dir_with(&["Documents/", "notes.txt"]);
        let st = test_state(dir.clone());
        let reps = replacements(&st, "cd Doc", 6);
        assert!(
            reps.iter().any(|r| r.starts_with("Documents")),
            "expected Documents, got {reps:?}"
        );
    }

    #[test]
    fn cd_argument_skips_files() {
        let dir = temp_dir_with(&["notes.txt"]);
        let st = test_state(dir);
        let reps = replacements(&st, "cd no", 5);
        assert!(reps.is_empty());
    }

    #[test]
    fn completes_export_env_names() {
        let st = test_state(PathBuf::from("."));
        let reps = replacements(&st, "export HO", 9);
        assert!(reps.iter().any(|r| r == "HOME"));
    }

    #[test]
    fn completes_dollar_variables() {
        let st = test_state(PathBuf::from("."));
        let reps = replacements(&st, "$HO", 3);
        assert!(reps.iter().any(|r| r == "$HOME"));
    }

    #[test]
    fn completes_quoted_dollar_variables() {
        let st = test_state(PathBuf::from("."));
        let line = "echo \"$HO";
        let reps = replacements(&st, line, line.len());
        assert!(
            reps.iter().any(|r| r.contains("$HOME")),
            "expected quoted $HOME completion, got {reps:?}"
        );
    }

    #[test]
    fn completes_quoted_paths() {
        let dir = temp_dir_with(&["Documents/"]);
        let st = test_state(dir);
        let line = "cd \"Doc";
        let reps = replacements(&st, line, line.len());
        assert!(
            reps.iter().any(|r| r.starts_with("Documents")),
            "expected Documents in quotes, got {reps:?}"
        );
    }

    #[test]
    fn completes_cd_minus_when_oldpwd_set() {
        let mut st = test_state(PathBuf::from("."));
        st.prev_cwd = Some(PathBuf::from("/old"));
        let reps = replacements(&st, "cd -", 4);
        assert!(reps.iter().any(|r| r == "-"));
    }

    #[test]
    fn completes_path_executables() {
        let bin_dir = temp_dir_with(&[]);
        #[cfg(windows)]
        fs::write(bin_dir.join("dsh-test-cmd.exe"), "").unwrap();
        #[cfg(not(windows))]
        {
            use std::os::unix::fs::PermissionsExt;
            let path = bin_dir.join("dsh-test-cmd");
            fs::write(&path, "").unwrap();
            let mut perms = fs::metadata(&path).unwrap().permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&path, perms).unwrap();
        }

        let mut st = test_state(PathBuf::from("."));
        st.env
            .insert("PATH".into(), bin_dir.to_string_lossy().into_owned());
        let reps = replacements(&st, "dsh-te", 6);
        assert!(
            reps.iter().any(|r| r == "dsh-test-cmd"),
            "expected dsh-test-cmd, got {reps:?}"
        );
    }

    #[test]
    fn completes_help_builtin_argument() {
        let st = test_state(PathBuf::from("."));
        let reps = replacements(&st, "help c", 6);
        assert!(reps.iter().any(|r| r == "cd"));
    }

    #[test]
    fn parse_handles_quoted_words() {
        let parse = parse_for_completion("echo \"hello world\" foo", 22);
        assert_eq!(parse.words, vec!["echo", "hello world"]);
        assert_eq!(parse.current, "foo");
        assert_eq!(parse.word_index, 2);
    }

    #[test]
    fn split_dir_and_prefix_handles_nested_relative() {
        let (dir, prefix) = split_dir_and_prefix(Path::new("/base"), "sub/prefix");
        assert_eq!(prefix, "prefix");
        assert!(dir.ends_with("sub"));
    }

    #[cfg(windows)]
    #[test]
    fn completes_documents_junction_in_user_home() {
        let home = dirs::home_dir().expect("home dir");
        let st = test_state(home);
        let reps = replacements(&st, "cd Doc", 6);
        assert!(
            reps.iter()
                .any(|r| r.to_ascii_lowercase().starts_with("documents")),
            "expected Documents junction, got {reps:?}"
        );
    }
}
