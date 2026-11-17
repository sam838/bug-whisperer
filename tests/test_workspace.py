"""Setting up a project folder (init) and checking the setup (doctor). No credits, no Chrome."""
import json
import subprocess

from whisperer import kane, workspace
from whisperer.detective import App
from whisperer.paths import PACKAGE


def test_sample_is_the_clinic_as_first_written_with_its_bugs(tmp_path):
    done = workspace.init_sample(tmp_path)
    original = (PACKAGE.parent / "demo" / "clinic_original_app.py").read_text(encoding="utf-8")
    assert (tmp_path / "clinic" / "app.py").read_text(encoding="utf-8") == original
    assert (tmp_path / "clinic" / "seed.py").is_file() and (tmp_path / "clinic" / "templates").is_dir()
    assert not list((tmp_path / "clinic").glob("*.db"))
    assert App.load(tmp_path / "apps" / "clinic.json").name == "Clinic Records"
    assert (tmp_path / "runs").is_dir()
    ignored = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert "runs/" in ignored and "apps/secrets/" in ignored
    assert len(done) == 2


def test_sample_never_overwrites_what_is_there(tmp_path):
    workspace.init_sample(tmp_path)
    (tmp_path / "clinic" / "app.py").write_text("# my changes", encoding="utf-8")
    again = workspace.init_sample(tmp_path)
    assert (tmp_path / "clinic" / "app.py").read_text(encoding="utf-8") == "# my changes"
    assert all("already here" in line for line in again)
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8").count("runs/") == 1


def test_your_own_app_keeps_passwords_out_of_its_file(tmp_path):
    path = workspace.init_app("My Shop", "http://localhost:3000", code="shop", start="npm start",
                              reset="npm run seed", login_path="/login", accounts=["Admin=admin@shop.test"],
                              folder=tmp_path, ask_password=lambda prompt: "s3cret")
    assert path == tmp_path / "apps" / "my-shop.json"
    assert "s3cret" not in path.read_text(encoding="utf-8")
    assert json.loads((tmp_path / "apps" / "secrets" / "my-shop.json").read_text(encoding="utf-8")) == {"Admin": "s3cret"}
    app = App.load(path)
    assert app.start == ["npm", "start"] and app.code_dir == "shop"
    assert app.variables()["account1_password"] == {"value": "s3cret", "secret": True}


def test_link_only_app_has_no_code_or_commands(tmp_path):
    data = json.loads(workspace.init_app("Docs", "https://example.com", folder=tmp_path).read_text(encoding="utf-8"))
    assert data == {"name": "Docs", "base_url": "https://example.com", "about": ""}


def test_bug_whisperer_itself_is_not_counted_as_a_connected_app(tmp_path):
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps" / "self.json").write_text(json.dumps({"name": "BW", "self_check": True}), encoding="utf-8")
    assert workspace.connected_apps(tmp_path) == []


def _answer(stdout, code=0):
    return lambda *a, **k: subprocess.CompletedProcess(a, code, stdout=stdout, stderr="")


def test_balance_reads_the_credits_past_kanes_notices(monkeypatch):
    monkeypatch.setattr(kane, "kane_binary", lambda: "kane-cli")
    monkeypatch.setattr(kane.subprocess, "run", _answer("Update available: 0.10.4 → 0.10.5\n\nAvailable credits: 9029.33\n"))
    assert kane.balance() == 9029.33


def test_no_credits_line_means_not_logged_in(monkeypatch):
    monkeypatch.setattr(kane, "kane_binary", lambda: "kane-cli")
    monkeypatch.setattr(kane.subprocess, "run", _answer("Error: please run kane-cli login\n", 1))
    assert kane.balance() is None


def test_doctor_blocks_without_kane_and_says_how_to_fix(monkeypatch):
    monkeypatch.setattr(kane, "version", lambda: None)
    checks = workspace.doctor()
    kane_check = next(c for c in checks if "Kane CLI" in c[1])
    assert kane_check[0] == "❌" and "npm install -g @testmuai/kane-cli" in kane_check[2]
