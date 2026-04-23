"""
Import ``app`` with Streamlit and filesystem mocked (no real UI run).
"""
import importlib
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class _SS(dict):
    """Dict with Streamlit-like attribute access for ``st.session_state``."""

    def __getattr__(self, k: str):
        if k in self:
            return self[k]
        raise AttributeError(k)

    def __setattr__(self, k: str, v) -> None:
        self[k] = v


def _fake_streamlit() -> types.ModuleType:
    m = types.ModuleType("streamlit")
    m.session_state = _SS()
    m.title = lambda *a, **k: None
    m.error = lambda *a, **k: None
    m.warning = lambda *a, **k: None
    m.stop = lambda *a, **k: None
    m.video = lambda *a, **k: None
    m.write = lambda *a, **k: None
    m.rerun = lambda *a, **k: None
    m.code = lambda *a, **k: None
    m.selectbox = lambda label, options, **kw: options[0]
    sb = types.SimpleNamespace()
    sb.caption = lambda *a, **k: None
    sb.code = lambda *a, **k: None
    sb.button = lambda *a, **k: False
    m.sidebar = sb
    return m


class TestAppImport(unittest.TestCase):
    def test_app_executes_with_mocks(self) -> None:
        m = _fake_streamlit()
        with patch.dict(sys.modules, {"streamlit": m}):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.listdir", return_value=["clip.mov"]),
                patch(
                    "logger.log_session_ui_events_for_video", MagicMock()
                ) as _log,
            ):
                for key in list(sys.modules):
                    if key == "app":
                        del sys.modules[key]
                import importlib as il

                _app = il.import_module("app")
        self.assertIn("clip.mov", _app.videos)
        _log.assert_called()
