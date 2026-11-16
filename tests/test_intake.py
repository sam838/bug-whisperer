"""Case intake: a tester's results become one case per problem. Claude and Kane are faked."""

import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from whisperer import detective, intake, web


@pytest.fixture
def runs(tmp_path, monkeypatch):
    for module in (detective, intake, web):
        monkeypatch.setattr(module, "RUNS", tmp_path)
    return tmp_path


def make_xlsx(path):
    shared = ('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<si><t>Test</t></si><si><t>Result</t></si><si><t>Book a past date</t></si><si><t>FAIL</t></si></sst>')
    sheet = ('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
             '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
             '<row r="2"><c r="A2" t="s"><v>2</v></c><c r="B2" t="s"><v>3</v></c><c r="C2"><v>42</v></c></row>'
             '</sheetData></worksheet>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", shared)
        z.writestr("xl/worksheets/sheet1.xml", sheet)


def make_docx(path):
    doc = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           '<w:p><w:r><w:t>Bug 1: </w:t></w:r><w:r><w:t>search shows nothing</w:t></w:r></w:p>'
           '<w:p><w:r><w:t>Bug 2: cart total is wrong</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", doc)


def test_spreadsheet_rows_are_read_without_extra_libraries(tmp_path):
    make_xlsx(tmp_path / "results.xlsx")
    assert intake.file_text(tmp_path / "results.xlsx") == "Test | Result\nBook a past date | FAIL | 42"


def test_word_paragraphs_are_read(tmp_path):
    make_docx(tmp_path / "report.docx")
    assert intake.file_text(tmp_path / "report.docx") == "Bug 1: search shows nothing\nBug 2: cart total is wrong"


def test_screenshots_and_pdfs_are_left_for_claude_to_look_at(tmp_path):
    (tmp_path / "a.png").write_bytes(b"png")
    assert intake.file_text(tmp_path / "a.png") is None


def test_a_broken_office_file_says_so_instead_of_crashing(tmp_path):
    (tmp_path / "bad.xlsx").write_bytes(b"not a zip")
    assert "couldn't read bad.xlsx" in intake.file_text(tmp_path / "bad.xlsx")


def test_each_problem_becomes_a_queued_case_with_its_screenshot(runs, monkeypatch):
    job = intake.Intake(app="Clinic Records", app_file="apps/clinic.json", note="from my test run")
    (job.folder / "results.csv").write_text("test,result\nbook past date,FAIL\nlogin,PASS\n", encoding="utf-8")
    (job.folder / "past.png").write_bytes(b"\x89PNG fake")
    job.files = ["results.csv", "past.png"]
    seen = {}

    def fake_claude(prompt, **kw):
        seen["prompt"] = prompt
        return {"problems": [{"title": "Past dates", "report": "Booking 3 March 2025 was saved.", "screenshot": "past.png"},
                             {"title": "Typo", "report": "The button says Sumbit.", "screenshot": ""}],
                "left_out": "1 passed test skipped."}
    monkeypatch.setattr(intake.claude, "ask_json", fake_claude)
    queued = []
    intake.run(job, lambda kind, inv_id: queued.append((kind, inv_id)))

    assert "book past date,FAIL" in seen["prompt"] and "past.png" in seen["prompt"]  # text read, image to look at
    assert job.status == "done" and len(job.cases) == 2 and job.left_out == "1 passed test skipped."
    assert queued == [("investigate", job.cases[0]), ("investigate", job.cases[1])]
    first = detective.Investigation(**{k: v for k, v in json.loads(
        (runs / job.cases[0] / "investigation.json").read_text(encoding="utf-8")).items()
        if k in detective.Investigation.__dataclass_fields__})
    assert first.status == "queued" and first.report == "Booking 3 March 2025 was saved."
    assert first.screenshot and first.screenshot.endswith("user-screenshot.png")
    assert intake.Intake.load(job.id).cases == job.cases


def test_the_public_demo_opens_at_most_three_cases_per_upload(runs, monkeypatch):
    monkeypatch.setattr(intake.demo, "hosted", lambda: True)
    monkeypatch.setattr(intake.demo, "count_job", lambda: None)
    job = intake.Intake(app="Clinic Records", app_file="apps/clinic.json")
    (job.folder / "r.txt").write_text("five bugs", encoding="utf-8")
    job.files = ["r.txt"]
    monkeypatch.setattr(intake.claude, "ask_json",
                        lambda p, **kw: {"problems": [{"report": f"bug {i}"} for i in range(5)]})
    intake.run(job, lambda kind, inv_id: None)
    assert len(job.cases) == 3


def test_uploading_test_results_starts_an_intake(runs, monkeypatch):
    monkeypatch.setattr(web, "enqueue", lambda kind, inv_id: None)
    started = []
    monkeypatch.setattr(web.intake, "run", lambda job, enqueue: started.append(job.id))
    client = TestClient(web.app)
    response = client.post("/report", data={"app_file": "apps/clinic.json", "report": ""},
                           files=[("files", ("results.csv", io.BytesIO(b"a,FAIL"), "text/csv"))],
                           follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"].startswith("/intake/")
    intake_id = response.headers["location"].rsplit("/", 1)[-1]
    page = client.get(f"/intake/{intake_id}").text
    assert "results.csv" in page and "Let me go through the tester" in page and "a,FAIL" in page


def test_one_screenshot_with_a_typed_report_is_still_one_case(runs, monkeypatch):
    monkeypatch.setattr(web, "enqueue", lambda kind, inv_id: None)
    client = TestClient(web.app)
    response = client.post("/report", data={"app_file": "apps/clinic.json", "report": "cant book"},
                           files=[("files", ("shot.png", io.BytesIO(b"\x89PNG"), "image/png"))],
                           follow_redirects=False)
    assert response.headers["location"].startswith("/r/")


def test_files_bug_whisperer_cant_read_are_refused(runs, monkeypatch):
    client = TestClient(web.app)
    response = client.post("/report", data={"app_file": "apps/clinic.json", "report": ""},
                           files=[("files", ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream"))])
    assert response.status_code == 400
