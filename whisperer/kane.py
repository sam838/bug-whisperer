"""Run Kane CLI and read its NDJSON stream.

Follows Kane's own parsing reference: skip non-JSON lines, ignore unknown event types,
take the verdict from the completion event, then confirm it with the exit code.
Exit 2 or 3, or a stream with no completion event, means Kane could not check:
that is reported as "error", never as a pass or a fail.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

COMPLETION_EVENTS = {"run_end", "test_md_done", "testrun_done", "remote_done"}


@dataclass
class KaneResult:
    verdict: str  # "passed" | "failed" | "error"
    exit_code: int
    status: str | None = None
    reason: str | None = None
    summary: str | None = None
    one_liner: str | None = None
    final_state: dict = field(default_factory=dict)
    session_dir: str | None = None
    test_url: str | None = None
    credits: float | None = None
    duration: float | None = None
    steps: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    ndjson_path: str | None = None
    kane_diagnosis: dict | None = None  # Kane's own bug verdict on a failed testmd step

    @property
    def failed_step(self) -> dict | None:
        return next((s for s in reversed(self.steps) if s.get("status") == "failed"), None)

    def to_dict(self) -> dict:
        data = self.__dict__.copy()
        data["failed_step"] = self.failed_step
        return data


def kane_binary() -> str:
    found = shutil.which("kane-cli")
    if not found:
        raise RuntimeError("kane-cli is not installed: npm install -g @testmuai/kane-cli")
    return found


def run(
    objective: str,
    *,
    url: str | None = None,
    variables: dict | None = None,
    max_steps: int = 15,
    timeout: int = 180,
    headless: bool = True,
    cdp_endpoint: str | None = None,
    name: str | None = None,
    log_path: Path | None = None,
    on_event: Callable[[dict], None] | None = None,
) -> KaneResult:
    """Run one plain-English objective with `kane-cli run --agent`.

    `name` saves the run as a Kane test (.testmuai/tests/<name>_test.md) that can be replayed.
    """
    argv = [kane_binary(), "run", objective, "--agent", "--max-steps", str(max_steps),
            "--timeout", str(timeout)]
    if name:
        argv += ["--name", name]
    if url:
        argv += ["--url", url]
    if variables:
        argv += ["--variables", json.dumps(variables)]
    if cdp_endpoint:
        argv += ["--cdp-endpoint", cdp_endpoint]
    elif headless:
        argv.append("--headless")
    return _execute(argv, timeout=timeout + 60, log_path=log_path, on_event=on_event)


def _execute(argv, *, timeout, log_path, on_event) -> KaneResult:
    env = {**os.environ, "KANE_CLI_USER_AGENT": "bug-whisperer"}
    started = time.time()
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
        text=True, encoding="utf-8", errors="replace", env=env,
    )
    steps: list[dict] = []
    errors: list[str] = []
    completion: dict | None = None
    diagnosis: dict | None = None
    log = open(log_path, "w", encoding="utf-8") if log_path else None
    try:
        for line in proc.stdout:  # type: ignore[union-attr]
            if log:
                log.write(line)
                log.flush()  # the website reads this file while Kane is still running
            event = _parse(line)
            if event is None:
                continue
            if on_event:
                on_event(event)
            kind = event.get("type")
            if kind in COMPLETION_EVENTS and completion is None:
                completion = event
            elif kind == "error":
                errors.append(str(event.get("message", "")))
            elif kind == "test_md_bug_verdict":
                diagnosis = event
            elif kind == "step_end" and event.get("status") in ("passed", "failed"):
                # testmd replays report steps as typed events with a summary, not progress lines
                steps.append({"step": event.get("index"),
                              "status": "done" if event["status"] == "passed" else "failed",
                              "remark": event.get("summary", "")})
            elif kind is None and "step" in event and event.get("status") in ("done", "failed"):
                steps.append(event)
            if time.time() - started > timeout:
                proc.kill()
                errors.append(f"bug-whisperer: killed Kane after {timeout}s")
                break
        proc.wait(timeout=30)
        stderr_tail = (proc.stderr.read() or "")[-2000:] if proc.stderr else ""
    finally:
        if log:
            log.close()

    exit_code = proc.returncode if proc.returncode is not None else 3
    result = KaneResult(verdict="error", exit_code=exit_code, steps=steps, errors=errors,
                        ndjson_path=str(log_path) if log_path else None)
    if completion:
        result.status = completion.get("status") or completion.get("overall_status")
        result.reason = completion.get("reason")
        result.summary = completion.get("summary")
        result.one_liner = completion.get("one_liner")
        result.final_state = completion.get("final_state") or {}
        result.session_dir = completion.get("session_dir")
        result.test_url = completion.get("test_url") or completion.get("share_url")
        result.credits = completion.get("credits_consumed", completion.get("credits"))
        result.duration = completion.get("duration") or completion.get("duration_s")

    result.kane_diagnosis = diagnosis
    automation_problem = bool(diagnosis and diagnosis.get("family") == "automation_bug")
    if completion and exit_code == 0 and result.status == "passed":
        result.verdict = "passed"
    elif completion and exit_code == 1 and result.status == "failed" and automation_problem:
        # Kane says the failure is in the test setup, not the app: that tells us nothing about the app.
        errors.append(f"Kane: automation problem, not an app bug: {diagnosis.get('one_liner')}")
    elif completion and exit_code == 1 and result.status == "failed":
        result.verdict = "failed"
    else:
        # Exit 2 (setup), 3 (timeout), no completion event, or a mismatch: Kane could not tell.
        if stderr_tail and not errors:
            errors.append(stderr_tail.strip().splitlines()[-1] if stderr_tail.strip() else "")
    return result


def _parse(line: str) -> dict | None:
    line = line.strip()
    if not line.startswith("{"):
        return None
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
