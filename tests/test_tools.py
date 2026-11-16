import numpy as np

from app.csv_loader import build_series, guess_columns, read_table
from app.ui.widgets import ASSETS
from tools.make_icon import SIZES, build_ico, read_ico_sizes, render_png
from tools.make_samples import make_samples

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_icon_sources_exist():
    for name in ("icon.svg", "icon_small.svg", "chevron.svg"):
        assert (ASSETS / name).is_file()


def test_png_is_rendered_with_blue_background_and_white_curve(qapp):
    from PyQt6.QtGui import QImage
    png = render_png(ASSETS / "icon.svg", 256)
    assert png.startswith(PNG_MAGIC)
    image = QImage.fromData(png)
    assert (image.width(), image.height()) == (256, 256)
    assert image.pixelColor(128, 230).name() == "#0a66d8"       # 地の青
    assert image.pixelColor(126, 60).name() == "#ffffff"        # 波形の山
    assert image.pixelColor(1, 1).alpha() == 0                  # 角は透明


def test_ico_contains_seven_sizes(qapp, tmp_path):
    path = tmp_path / "app.ico"
    build_ico(path)
    assert read_ico_sizes(path) == SIZES == [16, 24, 32, 48, 64, 128, 256]
    assert path.read_bytes().count(PNG_MAGIC) == 7


def test_samples_are_readable_by_the_app(tmp_path):
    paths = make_samples(tmp_path / "見本 データ")
    assert [p.name for p in paths] == ["sp_change.csv", "hunting.csv", "manual_step.csv"]
    for path, rows in zip(paths, (901, 901, 601)):
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")     # Excel で文字化けしない UTF-8（BOM 付き）
        table = read_table(path)
        cols = guess_columns(table.headers)
        assert cols == {"time": 0, "sp": 1, "out": 2, "pv": 3}
        s = build_series(table, cols["time"], cols["sp"], cols["out"], cols["pv"])
        assert len(s.t) == rows and s.dt == 1.0 and s.dropped == 0 and s.notes == []
    s = build_series(read_table(paths[0]), 0, 1, 2, 3)
    assert np.isclose(s.sp[0], 60.0) and np.isclose(s.sp[-1], 65.0)


def test_style_url_is_quoted():
    from app.ui.widgets import load_style
    s = load_style()
    assert 'url("' in s and 'chevron.svg")' in s
