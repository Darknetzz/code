from pathlib import Path

from mafibot.discover_diff import compare_html_files, write_discovery_report


def test_compare_html_files(tmp_path: Path):
    a = tmp_path / "a.html"
    b = tmp_path / "b.html"
    a.write_text("<html><body><p>Hello</p></body></html>", encoding="utf-8")
    b.write_text("<html><body><p>Bye</p></body></html>", encoding="utf-8")
    diff = compare_html_files(a, b)
    assert any("Hello" in line or "Bye" in line for line in diff)


def test_discovery_report(tmp_path: Path):
    run = tmp_path / "20260101_120000"
    run.mkdir()
    (run / "crime.html").write_text("<html><body>crime</body></html>", encoding="utf-8")
    report = write_discovery_report(run, [{"label": "Kriminalitet"}])
    text = report.read_text(encoding="utf-8")
    assert "Kriminalitet" in text
    assert "Discovery report" in text
