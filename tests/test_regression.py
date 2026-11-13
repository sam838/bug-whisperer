from whisperer.regression import strip_secrets

FRONT = """---
mode: testing
variables:
  global.account1_email:
    value: sunrise@example.com
    secret: false
    syntax: '{{account1_email}}'
  secrets.user.account1_password:
    value: sunrise123
    secret: true
    syntax: '{{account1_password}}'
---

# Session: x
"""


def test_secret_variables_are_removed_and_others_kept():
    out = strip_secrets(FRONT)
    assert "sunrise123" not in out
    assert "secrets.user.account1_password" not in out
    assert "value: sunrise@example.com" in out
    assert out.endswith("---\n\n# Session: x\n")


def test_blanked_secret_from_older_versions_is_removed_too():
    old = FRONT.replace("value: sunrise123", "value: ''")
    assert "account1_password" not in strip_secrets(old).split("---")[1]
