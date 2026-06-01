use std::collections::{HashMap, HashSet};

use eframe::egui;

use crate::path_model::{self, PathOrigin};
use crate::row_icons::mix_srgb;

use super::Scope;

pub(crate) fn origin_badge_label(origin: PathOrigin) -> &'static str {
    match origin {
        PathOrigin::Machine => "Machine",
        PathOrigin::User => "User",
    }
}

/// Row strip fill and accent color for path rows (Effective merged view; User tab = user tint; System tab = machine tint).
pub(crate) fn effective_origin_style(origin: PathOrigin) -> (egui::Color32, egui::Color32) {
    match origin {
        PathOrigin::Machine => (
            egui::Color32::from_rgb(26, 34, 52),
            egui::Color32::from_rgb(130, 185, 255),
        ),
        PathOrigin::User => (
            egui::Color32::from_rgb(34, 42, 30),
            egui::Color32::from_rgb(165, 215, 145),
        ),
    }
}

/// Fill, accent, and label colors for “add to user / machine” toolbar buttons (matches row strip hues).
pub(crate) fn origin_add_button_theme(origin: PathOrigin) -> (egui::Color32, egui::Color32, egui::Color32) {
    let (strip_fill, accent) = effective_origin_style(origin);
    let fill = mix_srgb(strip_fill, accent, 0.14);
    let text = egui::Color32::from_rgb(248, 248, 252);
    (fill, accent, text)
}

pub(crate) fn truncate_path_confirm(s: &str, max_chars: usize) -> String {
    let n = s.chars().count();
    if n <= max_chars {
        s.to_string()
    } else {
        s.chars().take(max_chars.saturating_sub(1)).collect::<String>() + "…"
    }
}

/// Row mark column: `[!]` missing, `[+]` also in the other store, `[n]` repeated in this section.
#[derive(Clone, Copy)]
pub(crate) enum PathMarkContext {
    SingleUser,
    SingleSystem,
    Effective(PathOrigin),
}

pub(crate) fn path_row_mark(
    warn: bool,
    cross_origin: bool,
    within_n: usize,
    ctx: PathMarkContext,
) -> (String, egui::Color32, Option<String>) {
    const WARN_C: egui::Color32 = egui::Color32::from_rgb(220, 180, 60);
    const CROSS_C: egui::Color32 = egui::Color32::from_rgb(190, 150, 255);
    const WITHIN_C: egui::Color32 = egui::Color32::from_rgb(130, 200, 255);

    if warn {
        return (
            "[!]".into(),
            WARN_C,
            Some("Path not found or not a directory (after expanding env vars)".into()),
        );
    }

    let mut lines: Vec<String> = Vec::new();
    if cross_origin {
        let line = match ctx {
            PathMarkContext::SingleUser => {
                "Also in system (machine) PATH — same path in both stores.".to_string()
            }
            PathMarkContext::SingleSystem => {
                "Also in user PATH — same path in both stores.".to_string()
            }
            PathMarkContext::Effective(PathOrigin::Machine) => {
                "Also in the user section — same path in both stores.".to_string()
            }
            PathMarkContext::Effective(PathOrigin::User) => {
                "Also in the machine (system) section — same path in both stores.".to_string()
            }
        };
        lines.push(line);
    }
    if within_n > 1 {
        let line = match ctx {
            PathMarkContext::SingleUser | PathMarkContext::SingleSystem => {
                format!("Same path appears {within_n} times in this list.")
            }
            PathMarkContext::Effective(PathOrigin::Machine) => {
                format!("Same path appears {within_n} times in machine (system) rows.")
            }
            PathMarkContext::Effective(PathOrigin::User) => {
                format!("Same path appears {within_n} times in user rows.")
            }
        };
        lines.push(line);
    }

    let tip = if lines.is_empty() {
        None
    } else {
        Some(lines.join("\n"))
    };

    if cross_origin {
        return ("[+]".into(), CROSS_C, tip);
    }
    if within_n > 1 {
        let label = if within_n <= 9 {
            format!("[{within_n}]")
        } else {
            "[9+]".into()
        };
        return (label, WITHIN_C, tip);
    }

    ("   ".into(), egui::Color32::TRANSPARENT, None)
}

pub(crate) fn mark_tooltip_with_filter_hint(base: Option<String>, interactive: bool) -> Option<String> {
    if !interactive {
        return base;
    }
    let hint =
        "Click mark to show only these rows (click again or “Show all rows” to clear).";
    Some(match base {
        Some(b) => format!("{b}\n\n{hint}"),
        None => hint.to_string(),
    })
}

pub(crate) fn effective_split_cross_and_counts(
    segments: &[(PathOrigin, String)],
) -> (HashSet<String>, HashMap<String, usize>, HashMap<String, usize>) {
    let (m_segs, u_segs) = path_model::split_origins(segments);
    (
        path_model::cross_origin_key_set(&m_segs, &u_segs),
        path_model::duplicate_key_counts(&m_segs),
        path_model::duplicate_key_counts(&u_segs),
    )
}

pub(crate) fn effective_row_is_duplicate(
    segments: &[(PathOrigin, String)],
    i: usize,
    cross_keys: &HashSet<String>,
    cnt_m: &HashMap<String, usize>,
    cnt_u: &HashMap<String, usize>,
) -> bool {
    let path_str = &segments[i].1;
    let key = path_model::path_duplicate_key(path_str);
    if key.is_empty() {
        return false;
    }
    let cross = cross_keys.contains(&key);
    let within_n = match segments[i].0 {
        PathOrigin::Machine => *cnt_m.get(&key).unwrap_or(&1),
        PathOrigin::User => *cnt_u.get(&key).unwrap_or(&1),
    };
    cross || within_n > 1
}

pub(crate) fn tab_row_is_duplicate(
    entries: &[String],
    i: usize,
    cross_keys_tab: &HashSet<String>,
    within_counts_tab: &HashMap<String, usize>,
) -> bool {
    let key = path_model::path_duplicate_key(&entries[i]);
    if key.is_empty() {
        return false;
    }
    let cross = cross_keys_tab.contains(&key);
    let within_n = *within_counts_tab.get(&key).unwrap_or(&1);
    cross || within_n > 1
}

pub(crate) fn tab_cross_keys_and_dup_counts(
    scope: Scope,
    entries: &[String],
    machine_for_cross: &[String],
    user_for_cross: &[String],
) -> (HashSet<String>, HashMap<String, usize>) {
    let cross_keys_tab = match scope {
        Scope::User => path_model::cross_origin_key_set(machine_for_cross, entries),
        Scope::System => path_model::cross_origin_key_set(entries, user_for_cross),
        Scope::Effective => HashSet::new(),
    };
    (cross_keys_tab, path_model::duplicate_key_counts(entries))
}

/// Multiset difference between saved vs pending entry lists (order ignored).
pub(crate) fn multiset_path_diff(baseline: &[String], pending: &[String]) -> (Vec<String>, Vec<String>) {
    let mut delta: HashMap<String, i32> = HashMap::new();
    for s in baseline {
        *delta.entry(s.clone()).or_insert(0) += 1;
    }
    for s in pending {
        *delta.entry(s.clone()).or_insert(0) -= 1;
    }
    let mut removed = Vec::new();
    let mut added = Vec::new();
    for (k, v) in delta {
        if v > 0 {
            for _ in 0..v {
                removed.push(k.clone());
            }
        } else if v < 0 {
            for _ in 0..(-v) {
                added.push(k.clone());
            }
        }
    }
    removed.sort();
    added.sort();
    (removed, added)
}

pub(crate) fn format_path_store_diff(title: &str, baseline: &[String], pending: &[String]) -> String {
    if baseline == pending {
        return format!("{title}\n  (no changes)\n\n");
    }
    let (removed, added) = multiset_path_diff(baseline, pending);
    if removed.is_empty() && added.is_empty() {
        return format!("{title}\n  Order changed only (same paths).\n\n");
    }
    let mut out = format!("{title}\n");
    if !removed.is_empty() {
        out.push_str("  Removed when saving:\n");
        for r in &removed {
            out.push_str(&format!("    − {}\n", r));
        }
    }
    if !added.is_empty() {
        out.push_str("  Added when saving:\n");
        for a in &added {
            out.push_str(&format!("    + {}\n", a));
        }
    }
    out.push('\n');
    out
}
