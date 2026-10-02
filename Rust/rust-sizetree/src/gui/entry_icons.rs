use egui::{Color32, Ui};
use egui_lucide::Lucide;

use crate::file_kind::file_icon_key;

pub fn entry_lucide(is_dir: bool, name: &str) -> Lucide {
    if is_dir {
        return Lucide::Folder;
    }
    match file_icon_key(name) {
        "file_code" => Lucide::FileCode,
        "file_image" => Lucide::FileImage,
        "file_video" => Lucide::FileVideoCamera,
        "file_audio" => Lucide::FileMusic,
        "file_archive" => Lucide::FileArchive,
        "file_pdf" => Lucide::FileType,
        "file_doc" => Lucide::FileText,
        "file_text" => Lucide::FileText,
        "file_html" => Lucide::Globe,
        "file_config" => Lucide::FileCog,
        "file_exec" => Lucide::Terminal,
        "file_spreadsheet" => Lucide::Sheet,
        _ => Lucide::File,
    }
}

/// Colors aligned with the HTML report entry-icon palette.
pub fn entry_color(is_dir: bool, name: &str) -> Color32 {
    if is_dir {
        return Color32::from_rgb(230, 190, 90);
    }
    match file_icon_key(name) {
        "file_code" => Color32::from_rgb(120, 220, 180),
        "file_image" => Color32::from_rgb(110, 210, 130),
        "file_video" => Color32::from_rgb(190, 120, 255),
        "file_audio" => Color32::from_rgb(80, 200, 220),
        "file_archive" => Color32::from_rgb(255, 150, 80),
        "file_pdf" => Color32::from_rgb(255, 120, 120),
        "file_doc" => Color32::from_rgb(255, 120, 120),
        "file_text" => Color32::from_rgb(160, 200, 255),
        "file_html" => Color32::from_rgb(255, 120, 120),
        "file_config" => Color32::from_rgb(163, 113, 247),
        "file_exec" => Color32::from_rgb(63, 185, 80),
        "file_spreadsheet" => Color32::from_rgb(63, 185, 80),
        _ => Color32::from_rgb(200, 200, 200),
    }
}

pub fn entry_icon(ui: &mut Ui, is_dir: bool, name: &str, size: f32) {
    let color = entry_color(is_dir, name);
    ui.add(entry_lucide(is_dir, name).size(size).color(color).image());
}
