use std::path::Path;

/// Open a local file in the user's default browser.
pub fn open_in_browser(path: &Path) -> bool {
    open::that(path).is_ok()
}
