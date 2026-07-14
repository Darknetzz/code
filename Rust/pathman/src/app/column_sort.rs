//! Clickable column headers and sort direction helpers.

use crate::path_model::PathOrigin;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SortDir {
    Asc,
    Desc,
}

impl SortDir {
    pub fn toggle(self) -> Self {
        match self {
            SortDir::Asc => SortDir::Desc,
            SortDir::Desc => SortDir::Asc,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum PathSortColumn {
    Mark,
    Origin,
    Path,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EnvSortColumn {
    Origin,
    Name,
    Value,
    Duplicate,
}

pub fn column_header(
    ui: &mut egui::Ui,
    label: &str,
    width: f32,
    active_dir: Option<SortDir>,
) -> egui::Response {
    let text = match active_dir {
        Some(SortDir::Asc) => format!("{label} ▲"),
        Some(SortDir::Desc) => format!("{label} ▼"),
        None => label.to_string(),
    };
    ui.add_sized(
        [width, ui.spacing().interact_size.y.max(22.0)],
        egui::Button::new(egui::RichText::new(text).small()),
    )
}

pub fn cmp_str_insensitive(a: &str, b: &str, dir: SortDir) -> std::cmp::Ordering {
    let ord = a.to_lowercase().cmp(&b.to_lowercase());
    match dir {
        SortDir::Asc => ord,
        SortDir::Desc => ord.reverse(),
    }
}

pub fn cmp_i32(a: i32, b: i32, dir: SortDir) -> std::cmp::Ordering {
    match dir {
        SortDir::Asc => a.cmp(&b),
        SortDir::Desc => b.cmp(&a),
    }
}

pub fn cmp_origin(a: PathOrigin, b: PathOrigin, dir: SortDir) -> std::cmp::Ordering {
    let ord = origin_rank(a).cmp(&origin_rank(b));
    match dir {
        SortDir::Asc => ord,
        SortDir::Desc => ord.reverse(),
    }
}

fn origin_rank(origin: PathOrigin) -> u8 {
    match origin {
        PathOrigin::Machine => 0,
        PathOrigin::User => 1,
    }
}

pub fn path_mark_score(warn_missing: bool, cross: bool, within_n: usize) -> i32 {
    let mut score = 0;
    if warn_missing {
        score += 100;
    }
    if cross {
        score += 50;
    }
    if within_n > 1 {
        score += 10 + within_n as i32;
    }
    score
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sort_dir_toggles() {
        assert_eq!(SortDir::Asc.toggle(), SortDir::Desc);
        assert_eq!(SortDir::Desc.toggle(), SortDir::Asc);
    }

    #[test]
    fn mark_score_orders_issues_first() {
        assert!(path_mark_score(true, false, 1) > path_mark_score(false, true, 1));
        assert!(path_mark_score(false, true, 1) > path_mark_score(false, false, 3));
    }
}
