//! Vector-drawn row action icons. Unicode glyphs are not reliable with egui's bundled fonts
//! (missing glyph → “tofu” boxes), so we paint triangles and an × with epaint.

use eframe::egui::{self, menu, Sense, Stroke, TextStyle, TextWrapMode, WidgetText};

pub(crate) fn mix_srgb(a: egui::Color32, b: egui::Color32, t: f32) -> egui::Color32 {
    let t = t.clamp(0.0, 1.0);
    egui::Color32::from_rgb(
        ((a.r() as f32) * (1.0 - t) + (b.r() as f32) * t).round() as u8,
        ((a.g() as f32) * (1.0 - t) + (b.g() as f32) * t).round() as u8,
        ((a.b() as f32) * (1.0 - t) + (b.b() as f32) * t).round() as u8,
    )
}

/// Folder / “add text” icons for the add-path toolbar (drawn, no font glyphs).
#[derive(Clone, Copy)]
pub enum AddToolbarIcon {
    Folder,
    TextRow,
}

fn paint_add_toolbar_icon(
    painter: &egui::Painter,
    rect: egui::Rect,
    icon: AddToolbarIcon,
    color: egui::Color32,
    line_w: f32,
) {
    let stroke = Stroke::new(line_w, color);
    let inner = rect.shrink(rect.width().min(rect.height()) * 0.14);
    match icon {
        AddToolbarIcon::Folder => {
            let tab_w = inner.width() * 0.52;
            let tab_h = inner.height() * 0.28;
            let tab = egui::Rect::from_min_size(
                inner.left_top() + egui::vec2(0.0, 0.0),
                egui::vec2(tab_w, tab_h),
            );
            let r = 1.2_f32;
            painter.rect_stroke(tab, r, stroke);
            let body = egui::Rect::from_min_max(
                egui::pos2(inner.left(), tab.bottom() - 0.5),
                inner.right_bottom(),
            );
            painter.rect_stroke(body, r, stroke);
        }
        AddToolbarIcon::TextRow => {
            let n = 3;
            let gap = inner.height() * 0.2;
            let line_h = ((inner.height() - gap * (n - 1) as f32) / n as f32).max(1.0);
            let w_full = inner.width() * 0.92;
            let w_short = inner.width() * 0.62;
            for i in 0..n {
                let y = inner.top() + i as f32 * (line_h + gap) + line_h * 0.5;
                let w = if i == n - 1 { w_short } else { w_full };
                let left = inner.left() + (inner.width() - w) * 0.5;
                let right = left + w;
                painter.line_segment(
                    [egui::pos2(left, y), egui::pos2(right, y)],
                    stroke,
                );
            }
        }
    }
}

/// Add-folder / add-text toolbar button with drawn icon and origin-colored chrome.
pub fn path_add_toolbar_button(
    ui: &mut egui::Ui,
    label: &str,
    icon: AddToolbarIcon,
    fill: egui::Color32,
    accent: egui::Color32,
    text_color: egui::Color32,
    tooltip: &str,
) -> egui::Response {
    let pad_x = 10.0_f32;
    let pad_y = 6.0_f32;
    let gap = 8.0_f32;
    let icon_side = 17.0_f32;
    let min_h = ui.spacing().interact_size.y;

    let galley = WidgetText::from(
        egui::RichText::new(label)
            .color(text_color)
            .text_style(TextStyle::Button),
    )
    .into_galley(
        ui,
        Some(TextWrapMode::Extend),
        f32::INFINITY,
        TextStyle::Button,
    );

    let w = pad_x + icon_side + gap + galley.size().x + pad_x;
    let h = (pad_y * 2.0 + galley.size().y)
        .max(pad_y * 2.0 + icon_side)
        .max(min_h);

    let (rect, response) = ui.allocate_exact_size(egui::vec2(w, h), Sense::click());
    if !ui.is_rect_visible(rect) {
        return response.on_hover_text(tooltip);
    }

    let hover = response.hovered();
    let bg = if hover {
        mix_srgb(fill, accent, 0.18)
    } else {
        fill
    };

    let rounding = ui.style().visuals.widgets.inactive.rounding;
    let painter = ui.painter_at(rect);
    painter.rect_filled(rect, rounding, bg);
    let stroke_color = mix_srgb(accent, egui::Color32::WHITE, if hover { 0.15 } else { 0.0 });
    painter.rect_stroke(rect, rounding, Stroke::new(1.0, stroke_color));

    let icon_rect = egui::Rect::from_center_size(
        egui::pos2(rect.left() + pad_x + icon_side * 0.5, rect.center().y),
        egui::vec2(icon_side, icon_side),
    );
    let line_w = (ui.style().visuals.widgets.inactive.fg_stroke.width * 1.4).max(1.2);
    paint_add_toolbar_icon(&painter, icon_rect, icon, accent, line_w);

    let text_pos = egui::pos2(
        rect.left() + pad_x + icon_side + gap,
        rect.center().y - 0.5 * galley.size().y,
    );
    painter.galley(text_pos, galley, text_color);

    response.on_hover_text(tooltip)
}

/// Origin-colored menu button (e.g. “User ▾” / “Machine ▾”) with a dropdown for add actions.
pub fn path_add_origin_menu<R>(
    ui: &mut egui::Ui,
    origin_label: &str,
    fill: egui::Color32,
    accent: egui::Color32,
    text_color: egui::Color32,
    tooltip: &str,
    add_contents: impl FnOnce(&mut egui::Ui) -> R,
) -> egui::InnerResponse<Option<R>> {
    let min_h = ui.spacing().interact_size.y;
    let btn = egui::Button::new(
        egui::RichText::new(format!("{origin_label} ▾"))
            .color(text_color)
            .text_style(TextStyle::Button),
    )
    .fill(fill)
    .stroke(Stroke::new(1.0, accent))
    .min_size(egui::vec2(0.0, min_h));

    let mut ir = menu::menu_custom_button(ui, btn, add_contents);
    ir.response = ir.response.on_hover_text(tooltip);
    ir
}

#[derive(Clone, Copy)]
pub enum PathRowIcon {
    MoveUp,
    MoveDown,
    OpenDirectory,
    Remove,
}

/// Small toolbar button with a drawn icon (no font glyphs required).
pub fn path_row_icon_button(
    ui: &mut egui::Ui,
    btn_size: [f32; 2],
    icon: PathRowIcon,
    tooltip: &str,
) -> egui::Response {
    let size = egui::vec2(btn_size[0], btn_size[1]);
    let response = ui.allocate_response(size, Sense::click());
    let rect = response.rect;

    if ui.is_rect_visible(rect) {
        let visuals = ui.style().interact(&response);
        let painter = ui.painter_at(rect);

        painter.rect(
            rect,
            visuals.rounding,
            visuals.weak_bg_fill,
            visuals.bg_stroke,
        );

        let pad = (rect.width().min(rect.height()) * 0.20).max(3.0);
        let inner = rect.shrink(pad);
        let line_width = (visuals.fg_stroke.width * 1.35).max(1.2);
        let stroke_color = match icon {
            PathRowIcon::Remove => egui::Color32::from_rgb(235, 95, 95),
            _ => visuals.fg_stroke.color,
        };
        let stroke = Stroke::new(line_width, stroke_color);

        match icon {
            PathRowIcon::MoveUp => {
                let top = egui::pos2(inner.center().x, inner.top());
                let bl = egui::pos2(inner.left(), inner.bottom());
                let br = egui::pos2(inner.right(), inner.bottom());
                painter.add(egui::Shape::closed_line(vec![top, bl, br], stroke));
            }
            PathRowIcon::MoveDown => {
                let tl = egui::pos2(inner.left(), inner.top());
                let tr = egui::pos2(inner.right(), inner.top());
                let bottom = egui::pos2(inner.center().x, inner.bottom());
                painter.add(egui::Shape::closed_line(vec![tl, tr, bottom], stroke));
            }
            PathRowIcon::OpenDirectory => {
                // Small folder (tab + body) with a “launch” arrow, same style as add-toolbar folder.
                let tab_w = inner.width() * 0.5;
                let tab_h = inner.height() * 0.28;
                let tab = egui::Rect::from_min_size(
                    inner.left_top() + egui::vec2(0.0, 0.0),
                    egui::vec2(tab_w, tab_h),
                );
                let r = 1.0_f32;
                painter.rect_stroke(tab, r, stroke);
                let body = egui::Rect::from_min_max(
                    egui::pos2(inner.left(), tab.bottom() - 0.5),
                    inner.right_bottom() - egui::vec2(inner.width() * 0.22, 0.0),
                );
                painter.rect_stroke(body, r, stroke);
                // Arrow: out from folder (bottom-right of icon).
                let a0 = body.right_bottom() - egui::vec2(body.width() * 0.45, body.height() * 0.55);
                let a1 = inner.right_top() - egui::vec2(inner.width() * 0.12, inner.height() * 0.15);
                painter.line_segment([a0, a1], stroke);
                let head = 2.5_f32;
                painter.line_segment(
                    [
                        a1,
                        a1 - egui::vec2(head, head * 0.45),
                    ],
                    stroke,
                );
                painter.line_segment(
                    [
                        a1,
                        a1 - egui::vec2(head * 0.45, head),
                    ],
                    stroke,
                );
            }
            PathRowIcon::Remove => {
                let inset = inner.width().min(inner.height()) * 0.22;
                let tl = inner.left_top() + egui::vec2(inset, inset);
                let br = inner.right_bottom() - egui::vec2(inset, inset);
                let tr = egui::pos2(inner.right() - inset, inner.top() + inset);
                let bl = egui::pos2(inner.left() + inset, inner.bottom() - inset);
                painter.add(egui::Shape::line_segment([tl, br], stroke));
                painter.add(egui::Shape::line_segment([tr, bl], stroke));
            }
        }
    }

    response.on_hover_text(tooltip)
}
