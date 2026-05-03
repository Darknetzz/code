//! Vector-drawn row action icons. Unicode glyphs are not reliable with egui's bundled fonts
//! (missing glyph → “tofu” boxes), so we paint triangles and an × with epaint.

use eframe::egui::{self, Sense, Stroke};

#[derive(Clone, Copy)]
pub enum PathRowIcon {
    MoveUp,
    MoveDown,
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
        let stroke = Stroke::new(
            (visuals.fg_stroke.width * 1.35).max(1.2),
            visuals.fg_stroke.color,
        );

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
