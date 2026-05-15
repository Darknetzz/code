use crate::ast::{Word, WordPart};
use crate::shell::ShellState;
use anyhow::Result;

pub fn expand_word(st: &ShellState, w: &Word) -> Result<String> {
    let mut out = String::new();
    for p in &w.0 {
        match p {
            WordPart::Literal(s) => out.push_str(s),
            WordPart::Var(name) => out.push_str(&expand_var(st, name)?),
        }
    }
    Ok(out)
}

fn expand_var(st: &ShellState, name: &str) -> Result<String> {
    Ok(match name {
        "?" => st.last_status.to_string(),
        "$" => std::process::id().to_string(),
        "#" => st.positional.len().to_string(),
        n if n.chars().all(|c| c.is_ascii_digit()) => {
            let idx = n.parse::<usize>().unwrap_or(0);
            if idx == 0 {
                st.argv0.clone()
            } else {
                st.positional
                    .get(idx.saturating_sub(1))
                    .cloned()
                    .unwrap_or_default()
            }
        }
        other => st.get_var(other).unwrap_or_default(),
    })
}
