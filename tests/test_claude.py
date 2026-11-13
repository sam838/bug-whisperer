from whisperer.claude import extract_json


def test_reads_fenced_json():
    text = 'Here you go:\n```json\n{"enough_info": true, "objective": "Go to x"}\n```'
    assert extract_json(text) == {"enough_info": True, "objective": "Go to x"}


def test_reads_bare_json_with_text_around():
    assert extract_json('Sure. {"reproduced": false} Done.') == {"reproduced": False}


def test_unreadable_answer_is_kept_not_guessed():
    assert "_unparsed" in extract_json("I could not decide.")
