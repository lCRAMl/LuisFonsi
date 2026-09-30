from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[1] / "src" / "palletizer" / "app.py"


def test_app_runs_without_errors():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert "EU36" in at.title[0].value
    assert at.metric[0].value == "5"


def test_app_pattern_change_and_error():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.sidebar.selectbox(key="pattern").set_value("EU05").run()
    assert not at.exception
    assert at.metric[0].value == "8"
    # Karton 680 x 260 passt nicht in 4x2 -> Überstandswarnung
    assert any("Überstand" in w.value for w in at.warning)


def test_app_assistant_takes_over_pattern():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.selectbox(key="assistant_choice").set_value("EU20").run()
    at.button[0].click().run()
    assert not at.exception
    assert "EU20" in at.title[0].value
