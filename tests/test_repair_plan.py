"""Claude's repair plan: code decides which parts of Claude's answer count. No Claude, no Kane."""
from whisperer import repair_plan
from whisperer.detective import App

APP = App(name="Clinic Records", base_url="http://127.0.0.1:8001",
          accounts={"Reception": {"email": "desk@clinic.test", "password": "hunter2-secret"}}, code_dir="clinic")
GOOD_SEALED = ("Go to http://127.0.0.1:8001/login. Log in with {{account1_email}} and {{account1_password}}. "
               "Book Aisha for yesterday at 1430. Store what the page shows after that as 'what_happened'. "
               "Verify that the page refuses the booking.")


def code(tmp_path):
    folder = tmp_path / "clinic"
    (folder / "templates").mkdir(parents=True, exist_ok=True)
    (folder / "app.py").write_text("x = 1\n", encoding="utf-8")
    (folder / "templates" / "book.html").write_text("<form></form>\n", encoding="utf-8")
    return folder.resolve()


def option(title, files, recommended=False):
    return {"title": title, "change": f"{title}, in plain words.", "files": files, "tradeoff": "Some trade-off.",
            "recommended": recommended}


def test_only_ways_that_name_real_files_count_and_at_most_three(tmp_path):
    folder = code(tmp_path)
    raw = {"cause": "The server saves any date.", "options": [
        option("Guess", ["nowhere.py"]),
        option("Guard the door", ["clinic/app.py"], recommended=True),  # Claude named the folder too
        option("Guard the calendar", ["./templates/book.html", "../secrets.json"]),
        option("Both", ["app.py", "templates\\book.html"]),
        option("A fourth way", ["app.py"]),
    ]}
    plan = repair_plan.check(raw, folder, APP)
    assert plan["status"] == "ready" and plan["cause"] == "The server saves any date."
    assert [o["id"] for o in plan["options"]] == ["A", "B", "C"]
    assert [o["title"] for o in plan["options"]] == ["Guard the door", "Guard the calendar", "Both"]
    assert plan["options"][0]["files"] == ["app.py"]
    assert plan["options"][1]["files"] == ["templates/book.html"]  # the path outside the code is dropped
    assert plan["recommended"] == "A" and [o["recommended"] for o in plan["options"]] == [True, False, False]


def test_without_a_marked_pick_the_first_way_is_recommended(tmp_path):
    plan = repair_plan.check({"options": [option("One", ["app.py"]), option("Two", ["app.py"])]}, code(tmp_path), APP)
    assert plan["recommended"] == "A"


def test_a_plan_with_no_real_file_is_set_aside(tmp_path):
    plan = repair_plan.check({"cause": "?", "options": [option("Guess", ["nowhere.py"])]}, code(tmp_path), APP)
    assert plan["status"] == "error" and "no files" in plan["error"]
    assert repair_plan.check({"_unparsed": "sorry"}, code(tmp_path), APP)["status"] == "error"


def test_the_sealed_question_must_be_a_usable_kane_objective():
    good = repair_plan.sealed_question({"objective": GOOD_SEALED, "why": "Yesterday, not last year."}, APP)
    assert good == {"objective": GOOD_SEALED, "why": "Yesterday, not last year."}
    bad = [
        GOOD_SEALED.replace("http://127.0.0.1:8001", "http://elsewhere.test"),   # not the app
        GOOD_SEALED.replace("Verify that the page refuses the booking.", "Done."),  # no check
        GOOD_SEALED + " Verify that it says why.",                               # two checks
        GOOD_SEALED.replace("{{account1_password}}", "hunter2-secret"),          # a real password
        "",
    ]
    for objective in bad:
        assert repair_plan.sealed_question({"objective": objective}, APP) is None, objective
    assert repair_plan.sealed_question({"objective": GOOD_SEALED}, APP, objective=GOOD_SEALED) is None  # same steps
    assert repair_plan.sealed_question("just a string", APP) is None


def test_choose_takes_the_persons_pick_or_claudes(tmp_path):
    plan = repair_plan.check({"options": [option("One", ["app.py"]), option("Two", ["app.py"], recommended=True)]},
                             code(tmp_path), APP)
    assert repair_plan.choose(plan, "a")["title"] == "One"
    assert repair_plan.choose(plan, None)["title"] == "Two"
    assert repair_plan.choose(plan, "Z")["title"] == "Two"
    assert repair_plan.choose(None, "A") is None


def test_kept_word_compares_the_plan_with_the_real_diff():
    patch = "--- a/clinic/app.py\n+++ b/clinic/app.py\n+if past: refuse\n"
    kept = repair_plan.kept_word(["app.py"], patch)
    assert kept["kept"] and kept["touched"] == ["clinic/app.py"] and kept["extra"] == []
    strayed = repair_plan.kept_word(["app.py"], patch + "--- a/clinic/models.py\n+++ b/clinic/models.py\n+x\n")
    assert not strayed["kept"] and strayed["extra"] == ["clinic/models.py"]
    nothing = repair_plan.kept_word(["app.py"], "")
    assert not nothing["kept"] and nothing["unused"] == ["app.py"]
    assert repair_plan.promise_line(nothing).startswith("No: the repair changed no files")
    assert repair_plan.promise_line(strayed).startswith("No: it also changed clinic/models.py")
    deleted = repair_plan.kept_word(["old.py"], "--- a/clinic/old.py\n+++ /dev/null\n-x\n")
    assert deleted["kept"] and deleted["touched"] == ["clinic/old.py"]
