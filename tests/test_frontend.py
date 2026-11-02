from pathlib import Path

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from backend.main import create_app


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_editor_and_study_end_to_end(tmp_path, monkeypatch):
    client = TestClient(create_app(tmp_path))

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        response = client.request(method, url.removeprefix("http://127.0.0.1:8000"), **kwargs)
        # requests.Response exposes ok, unlike httpx.Response.
        response.ok = response.is_success
        return response

    monkeypatch.setattr("requests.request", request)
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "frontend/app.py"), default_timeout=20).run()
    assert not app.exception
    app.text_input[0].set_value("Operating Systems")
    button(app, "Create deck").click().run()
    assert not app.exception
    app.text_area[0].set_value("What is an OS?")
    app.text_area[1].set_value("Software that manages hardware.")
    button(app, "Create root card").click().run()
    assert not app.exception
    # Root creation form is followed by selected-card editing and child creation.
    app.text_area[-2].set_value("What is a process?")
    app.text_area[-1].set_value("A running program.")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    assert app.selectbox[0].value is not None
    app.text_area[-2].set_value("What is a thread?")
    app.text_area[-1].set_value("A unit of execution.")
    button(app, "Add Child Card").click().run()
    assert not app.exception
    app.text_area[2].set_value("What is a hardware thread?")
    button(app, "Save changes").click().run()
    assert not app.exception
    button(app, "Study").click().run()
    assert not app.exception
    assert app.subheader[0].value == "What is an OS?"
    button(app, "Flip").click().run()
    button(app, "What is a process?").click().run()
    assert app.subheader[0].value == "What is a process?"
    button(app, "Continue").click().run()
    assert app.subheader[0].value == "What is a hardware thread?"
    button(app, "Continue").click().run()
    assert app.success[0].value.startswith("Session complete")
    button(app, "Restart session").click().run()
    assert app.subheader[0].value == "What is an OS?"
    assert not app.exception
