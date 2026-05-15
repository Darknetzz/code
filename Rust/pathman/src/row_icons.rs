//! Vector-drawn row action icons. Unicode glyphs are not reliable with egui's bundled fonts
//! (missing glyph → “tofu” boxes), so we paint triangles and an × with epaint.

use eframe::egui::{self, menu, Sense, Stroke, TextStyle, TextWrapMode, WidgetText};

/// Pixel gap between drawn icons and their labels (toolbar add buttons and origin menus).
const ICON_TEXT_GAP: f32 = 8.0;
/// Right edge of the drawn “+” in `path_add_origin_menu` from the button rect’s left (center `pad + 7`, size 12).
const ORIGIN_MENU_PLUS_RIGHT: f32 = 7.0 + 6.0;

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
    let gap = ICON_TEXT_GAP;
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

/// Small filled ▼ drawn with epaint (no font glyphs — Unicode arrows often missing in egui fonts).
fn paint_dropdown_chevron(painter: &egui::Painter, rect: egui::Rect, fill: egui::Color32) {
    let tri = egui::Rect::from_center_size(
        rect.center(),
        egui::vec2(rect.width() * 0.95, rect.height() * 0.85),
    );
    painter.add(egui::Shape::convex_polygon(
        vec![
            tri.left_top(),
            tri.right_top(),
            tri.center_bottom(),
        ],
        fill,
        Stroke::NONE,
    ));
}

/// Ascii “+” not used — small drawn plus, same idea as other toolbar icons.
fn paint_add_plus(painter: &egui::Painter, rect: egui::Rect, color: egui::Color32, line_w: f32) {
    let stroke = Stroke::new(line_w, color);
    let inner = rect.shrink(rect.width().min(rect.height()) * 0.2);
    let cy = inner.center().y;
    let cx = inner.center().x;
    painter.line_segment(
        [egui::pos2(inner.left(), cy), egui::pos2(inner.right(), cy)],
        stroke,
    );
    painter.line_segment(
        [egui::pos2(cx, inner.top()), egui::pos2(cx, inner.bottom())],
        stroke,
    );
}

/// Origin-colored menu button (e.g. “Add user…”) with a dropdown for add actions.
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
    // Leading spaces clear room for the drawn “+” and `ICON_TEXT_GAP` after it (same as toolbar).
    let space_w = WidgetText::from(egui::RichText::new(" ").text_style(TextStyle::Button))
        .into_galley(
            ui,
            Some(TextWrapMode::Extend),
            f32::INFINITY,
            TextStyle::Button,
        )
        .size()
        .x
        .max(1.0);
    let min_leading_px = ORIGIN_MENU_PLUS_RIGHT + ICON_TEXT_GAP;
    let n_spaces = ((min_leading_px / space_w).ceil() as usize).max(1);
    let label = format!("{}{}", " ".repeat(n_spaces), origin_label);
    let line_w = (ui.style().visuals.widgets.inactive.fg_stroke.width * 1.4).max(1.2);
    // `shortcut_text` reserves the right strip so the label stays left-aligned; we paint the chevron
    // there (spaces are nearly invisible at weak_text_color).
    let btn = egui::Button::new(
        egui::RichText::new(label)
            .color(text_color)
            .text_style(TextStyle::Button),
    )
    .fill(fill)
    .stroke(Stroke::new(1.0, accent))
    .min_size(egui::vec2(0.0, min_h))
    .shortcut_text("    ");

    let mut ir = menu::menu_custom_button(ui, btn, add_contents);

    let r = ir.response.rect;
    let pad = ui.spacing().button_padding.x;
    let chev = egui::Rect::from_center_size(
        egui::pos2(r.right() - pad - 9.0, r.center().y),
        egui::vec2(10.0, 7.0),
    );
    if ui.is_rect_visible(r) {
        let painter = ui.painter_at(r);
        let plus_r = egui::Rect::from_center_size(
            egui::pos2(r.left() + pad + 7.0, r.center().y),
            egui::vec2(12.0, 12.0),
        );
        paint_add_plus(&painter, plus_r, text_color, line_w);
        paint_dropdown_chevron(&painter, chev, text_color);
    }

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

// --- Top panel (icon + label, default widget chrome; drawn icons only) ---

const TOP_BAR_PAD_X: f32 = 8.0;
const TOP_BAR_ICON: f32 = 15.0;

#[derive(Clone, Copy)]
pub enum TopBarIcon {
    Reload,
    Save,
    Changes,
    Dedupe,
    Duplicates,
    FilterDuplicates,
    FilterMissing,
    ScopeEffective,
    ScopeUser,
    ScopeSystem,
    /// Shell rc snippet file (Unix `Shell file…` top bar control).
    #[cfg(not(windows))]
    ShellFile,
}

fn paint_top_bar_icon(
    painter: &egui::Painter,
    rect: egui::Rect,
    icon: TopBarIcon,
    color: egui::Color32,
    line_w: f32,
) {
    let stroke = Stroke::new(line_w, color);
    let inner = rect.shrink(rect.width().min(rect.height()) * 0.12);
    match icon {
        TopBarIcon::Reload => {
            let c = inner.center();
            let r = inner.width().min(inner.height()) * 0.38;
            let steps = 18;
            let start = -0.35 * std::f32::consts::PI;
            let sweep = 1.55 * std::f32::consts::TAU;
            let mut pts = Vec::with_capacity(steps + 1);
            for i in 0..=steps {
                let t = start + sweep * (i as f32 / steps as f32);
                pts.push(c + r * egui::vec2(t.cos(), t.sin()));
            }
            let tail = (pts.len() >= 2).then(|| {
                (pts[pts.len() - 2], *pts.last().expect("len >= 2"))
            });
            painter.add(egui::Shape::line(pts, stroke));
            if let Some((p1, p2)) = tail {
                let dir = (p2 - p1).normalized();
                let ah = r * 0.42;
                let orth = egui::vec2(-dir.y, dir.x);
                painter.line_segment([p2, p2 - dir * ah + orth * ah * 0.45], stroke);
                painter.line_segment([p2, p2 - dir * ah - orth * ah * 0.45], stroke);
            }
        }
        TopBarIcon::Save => {
            let body = egui::Rect::from_min_max(
                inner.left_bottom() + egui::vec2(inner.width() * 0.08, -inner.height() * 0.62),
                inner.right_bottom() - egui::vec2(inner.width() * 0.08, inner.height() * 0.08),
            );
            let tab = egui::Rect::from_min_max(
                egui::pos2(body.left(), body.top() - inner.height() * 0.28),
                egui::pos2(body.right(), body.top()),
            );
            painter.rect_stroke(tab, 1.0, stroke);
            painter.rect_stroke(body, 1.2, stroke);
            let slit_w = body.width() * 0.35;
            painter.line_segment(
                [
                    egui::pos2(body.center().x - slit_w * 0.5, body.center().y),
                    egui::pos2(body.center().x + slit_w * 0.5, body.center().y),
                ],
                stroke,
            );
        }
        TopBarIcon::Changes => {
            let y0 = inner.top() + inner.height() * 0.22;
            let y1 = inner.center().y;
            let y2 = inner.bottom() - inner.height() * 0.22;
            let w_full = inner.width() * 0.88;
            let w_mid = inner.width() * 0.72;
            let w_short = inner.width() * 0.52;
            for (y, w) in [(y0, w_full), (y1, w_mid), (y2, w_short)] {
                let left = inner.center().x - w * 0.5;
                painter.line_segment(
                    [egui::pos2(left, y), egui::pos2(left + w, y)],
                    stroke,
                );
            }
        }
        TopBarIcon::Dedupe => {
            let y1 = inner.top() + inner.height() * 0.28;
            let y2 = inner.bottom() - inner.height() * 0.28;
            let xl = inner.left() + inner.width() * 0.18;
            let xr = inner.right() - inner.width() * 0.18;
            let xm = inner.center().x;
            painter.line_segment([egui::pos2(xl, y1), egui::pos2(xm, y2)], stroke);
            painter.line_segment([egui::pos2(xr, y1), egui::pos2(xm, y2)], stroke);
            painter.line_segment(
                [
                    egui::pos2(xm - inner.width() * 0.22, y2),
                    egui::pos2(xm + inner.width() * 0.22, y2),
                ],
                stroke,
            );
        }
        TopBarIcon::Duplicates => {
            let a = inner.shrink2(egui::vec2(inner.width() * 0.12, inner.height() * 0.18));
            let shift = inner.width().min(inner.height()) * 0.14;
            let r1 = a.translate(egui::vec2(-shift * 0.35, shift * 0.35));
            let r2 = a.translate(egui::vec2(shift * 0.35, -shift * 0.35));
            painter.rect_stroke(r1, 1.0, stroke);
            painter.rect_stroke(r2, 1.0, stroke);
        }
        TopBarIcon::ScopeEffective => {
            let gap = inner.height() * 0.22;
            let h = (inner.height() - gap * 2.0) / 3.0;
            let w_top = inner.width() * 0.88;
            let w_mid = inner.width() * 0.68;
            let w_bot = inner.width() * 0.48;
            for (i, w) in [w_top, w_mid, w_bot].into_iter().enumerate() {
                let y = inner.top() + i as f32 * (h + gap) + h * 0.5;
                let left = inner.center().x - w * 0.5;
                painter.line_segment(
                    [egui::pos2(left, y), egui::pos2(left + w, y)],
                    stroke,
                );
            }
        }
        TopBarIcon::ScopeUser => {
            let head_r = inner.width().min(inner.height()) * 0.22;
            let hc = egui::pos2(inner.center().x, inner.top() + head_r + inner.height() * 0.06);
            painter.circle_stroke(hc, head_r, stroke);
            let shoulders = egui::Rect::from_min_max(
                egui::pos2(inner.center().x - head_r * 1.1, hc.y + head_r * 0.65),
                egui::pos2(inner.center().x + head_r * 1.1, inner.bottom() - inner.height() * 0.06),
            );
            painter.add(egui::Shape::line_segment(
                [
                    shoulders.left_bottom(),
                    shoulders.right_bottom(),
                ],
                stroke,
            ));
        }
        TopBarIcon::ScopeSystem => {
            let bezel = 1.0_f32;
            let scr = inner.shrink(inner.width().min(inner.height()) * 0.12);
            painter.rect_stroke(scr, bezel, stroke);
            let inner_scr = scr.shrink2(egui::vec2(scr.width() * 0.12, scr.height() * 0.18));
            painter.rect_stroke(inner_scr, 0.8, stroke);
            let foot_w = scr.width() * 0.28;
            let foot = egui::Rect::from_center_size(
                egui::pos2(scr.center().x, inner.bottom() - inner.height() * 0.06),
                egui::vec2(foot_w, inner.height() * 0.08),
            );
            painter.rect_stroke(foot, 0.5, stroke);
        }
        TopBarIcon::FilterDuplicates => {
            let top_w = inner.width() * 0.72;
            let bot_w = inner.width() * 0.38;
            let tl = inner.center().x - top_w * 0.5;
            let tr = tl + top_w;
            let y_top = inner.top() + inner.height() * 0.18;
            let y_bot = inner.bottom() - inner.height() * 0.18;
            let bl = inner.center().x - bot_w * 0.5;
            let br = bl + bot_w;
            painter.add(egui::Shape::closed_line(
                vec![
                    egui::pos2(tl, y_top),
                    egui::pos2(tr, y_top),
                    egui::pos2(br, y_bot),
                    egui::pos2(bl, y_bot),
                ],
                stroke,
            ));
        }
        TopBarIcon::FilterMissing => {
            let tab_w = inner.width() * 0.52;
            let tab_h = inner.height() * 0.22;
            let tab = egui::Rect::from_min_size(inner.left_top(), egui::vec2(tab_w, tab_h));
            painter.rect_stroke(tab, 1.0, stroke);
            let body = egui::Rect::from_min_max(
                egui::pos2(inner.left(), tab.bottom()),
                inner.right_bottom(),
            );
            painter.rect_stroke(body, 1.0, stroke);
            let q = body.center();
            let dot_r = (inner.width().min(inner.height()) * 0.08).max(1.0);
            painter.circle_filled(q, dot_r, color);
            painter.circle_stroke(q, dot_r * 2.2, stroke);
        }
        #[cfg(not(windows))]
        TopBarIcon::ShellFile => {
            let doc = inner.shrink(inner.width().min(inner.height()) * 0.1);
            painter.rect_stroke(doc, 1.0, stroke);
            let y0 = doc.top() + doc.height() * 0.32;
            let y1 = y0 + doc.height() * 0.16;
            let y2 = y1 + doc.height() * 0.14;
            let inset = doc.width() * 0.14;
            painter.line_segment(
                [
                    egui::pos2(doc.left() + inset, y0),
                    egui::pos2(doc.right() - inset, y0),
                ],
                stroke,
            );
            painter.line_segment(
                [
                    egui::pos2(doc.left() + inset, y1),
                    egui::pos2(doc.right() - inset * 2.2, y1),
                ],
                stroke,
            );
            painter.line_segment(
                [
                    egui::pos2(doc.left() + inset, y2),
                    egui::pos2(doc.right() - inset * 1.8, y2),
                ],
                stroke,
            );
        }
    }
}

/// Extra drawing for top-bar actions (e.g. **Save**).
#[derive(Clone, Copy, Default, PartialEq, Eq)]
pub enum TopBarButtonEmphasis {
    #[default]
    None,
    /// Mild primary tint so **Save** is easy to find when there is nothing to save yet.
    IdlePrimary,
    /// Warmer fill + stroke aligned with “Unsaved changes” (use when edits are pending).
    Unsaved,
}

/// Icon + text button using normal widget interaction (disabled state uses [`Ui::add_enabled_ui`]).
///
/// [`TopBarButtonEmphasis::IdlePrimary`] / [`TopBarButtonEmphasis::Unsaved`] adjust fill and stroke;
/// unsaved styling only applies when `enabled` is true.
pub fn path_top_bar_button(
    ui: &mut egui::Ui,
    label: &str,
    icon: TopBarIcon,
    enabled: bool,
    min_width: f32,
    tooltip: Option<&str>,
    emphasis: TopBarButtonEmphasis,
) -> egui::Response {
    let ir = ui.add_enabled_ui(enabled, |ui| {
        let min_h = ui.spacing().interact_size.y;
        let gap = ICON_TEXT_GAP;
        let icon_side = TOP_BAR_ICON;
        let pad_x = TOP_BAR_PAD_X;

        let galley = WidgetText::from(egui::RichText::new(label).text_style(TextStyle::Button))
            .into_galley(
                ui,
                Some(TextWrapMode::Extend),
                f32::INFINITY,
                TextStyle::Button,
            );

        let w = (pad_x + icon_side + gap + galley.size().x + pad_x).max(min_width);
        let h = (ui.spacing().button_padding.y * 2.0 + galley.size().y)
            .max(ui.spacing().button_padding.y * 2.0 + icon_side)
            .max(min_h);

        let (rect, response) = ui.allocate_exact_size(egui::vec2(w, h), Sense::click());
        if ui.is_rect_visible(rect) {
            let visuals = ui.style().interact(&response);
            let text_color = visuals.fg_stroke.color;
            let line_w = (visuals.fg_stroke.width * 1.35).max(1.2);
            let painter = ui.painter_at(rect);
            let unsaved_orange = egui::Color32::from_rgb(255, 165, 70);
            let sel = ui.visuals().selection.bg_fill;
            let (weak_fill, hover_fill, stroke) = match emphasis {
                TopBarButtonEmphasis::Unsaved if enabled => (
                    mix_srgb(visuals.weak_bg_fill, unsaved_orange, 0.32),
                    mix_srgb(visuals.bg_fill, unsaved_orange, 0.24),
                    Stroke::new(
                        (visuals.bg_stroke.width + 1.0).min(3.0),
                        mix_srgb(visuals.bg_stroke.color, unsaved_orange, 0.55),
                    ),
                ),
                TopBarButtonEmphasis::IdlePrimary => {
                    let t = if enabled { 0.14 } else { 0.09 };
                    (
                        mix_srgb(visuals.weak_bg_fill, sel, t),
                        mix_srgb(visuals.bg_fill, sel, t * 0.85),
                        Stroke::new(
                            (visuals.bg_stroke.width + 0.5).min(2.2),
                            mix_srgb(visuals.bg_stroke.color, sel, 0.35),
                        ),
                    )
                }
                _ => (visuals.weak_bg_fill, visuals.bg_fill, visuals.bg_stroke),
            };
            painter.rect_filled(rect, visuals.rounding, weak_fill);
            if response.hovered() || response.highlighted() || response.has_focus() {
                painter.rect_filled(rect, visuals.rounding, hover_fill);
            }
            painter.rect_stroke(rect, visuals.rounding, stroke);
            let icon_rect = egui::Rect::from_center_size(
                egui::pos2(rect.left() + pad_x + icon_side * 0.5, rect.center().y),
                egui::vec2(icon_side, icon_side),
            );
            paint_top_bar_icon(&painter, icon_rect, icon, text_color, line_w);
            let text_pos = egui::pos2(
                rect.left() + pad_x + icon_side + gap,
                rect.center().y - 0.5 * galley.size().y,
            );
            painter.galley(text_pos, galley, text_color);
        }
        match tooltip {
            Some(text) => response.on_hover_text(text),
            None => response,
        }
    });
    ir.inner
}

/// Icon + text selectable (scope tabs, filters).
pub fn path_top_bar_selectable(
    ui: &mut egui::Ui,
    selected: bool,
    label: &str,
    icon: TopBarIcon,
) -> egui::Response {
    let gap = ICON_TEXT_GAP;
    let icon_side = TOP_BAR_ICON;
    let pad_x = TOP_BAR_PAD_X;
    let min_h = ui.spacing().interact_size.y;

    let galley = WidgetText::from(egui::RichText::new(label).text_style(TextStyle::Button))
        .into_galley(
            ui,
            Some(TextWrapMode::Extend),
            f32::INFINITY,
            TextStyle::Button,
        );

    let w = pad_x + icon_side + gap + galley.size().x + pad_x;
    let h = (ui.spacing().button_padding.y * 2.0 + galley.size().y)
        .max(ui.spacing().button_padding.y * 2.0 + icon_side)
        .max(min_h);

    let (rect, response) = ui.allocate_exact_size(egui::vec2(w, h), Sense::click());
    if ui.is_rect_visible(rect) {
        let rounding = ui.visuals().widgets.inactive.rounding;
        let painter = ui.painter_at(rect);
        let bg = if selected {
            ui.visuals().selection.bg_fill
        } else if response.hovered() {
            ui.visuals().widgets.hovered.weak_bg_fill
        } else {
            egui::Color32::TRANSPARENT
        };
        if bg != egui::Color32::TRANSPARENT {
            painter.rect_filled(rect, rounding, bg);
        }
        let stroke = if selected {
            ui.visuals().selection.stroke
        } else {
            ui.visuals().widgets.inactive.bg_stroke
        };
        if selected {
            painter.rect_stroke(rect, rounding, stroke);
        }
        let text_color = if selected {
            ui.visuals().selection.stroke.color
        } else {
            ui.style().interact(&response).fg_stroke.color
        };
        let line_w = (ui.style().visuals.widgets.inactive.fg_stroke.width * 1.35).max(1.2);
        let icon_rect = egui::Rect::from_center_size(
            egui::pos2(rect.left() + pad_x + icon_side * 0.5, rect.center().y),
            egui::vec2(icon_side, icon_side),
        );
        paint_top_bar_icon(&painter, icon_rect, icon, text_color, line_w);
        let text_pos = egui::pos2(
            rect.left() + pad_x + icon_side + gap,
            rect.center().y - 0.5 * galley.size().y,
        );
        painter.galley(text_pos, galley, text_color);
    }
    response
}
