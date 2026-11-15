"""Execution harness for the unchanged issue #1578 reproducer.

Only test fixtures and evidence capture are supplied here. No changes to
workflow decisions, activity definitions, or scheduling are made.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import traceback
from types import SimpleNamespace
import uuid

from temporalio.client import WorkflowHistory
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

import issue_1578_original as original


def append_record(record):
    out = Path(os.environ.get("EVIDENCE_DIR", "evidence"))
    out.mkdir(parents=True, exist_ok=True)
    with (out / "results.jsonl").open("a", encoding="utf-8") as dest:
        dest.write(json.dumps(record, sort_keys=True) + "\n")
    print("EVIDENCE", json.dumps(record, sort_keys=True), flush=True)


@asynccontextmanager
async def new_worker(client, workflow_class, activities):
    queue = "temporal-replay-1578-" + str(uuid.uuid4())
    async with Worker(
        client, task_queue=queue, workflows=[workflow_class], activities=activities
    ):
        yield SimpleNamespace(task_queue=queue)


class HistoryCapturingReplayer:
    """Save history first, then invoke the SDK's Replayer twice."""

    def __init__(self, *args, **kwargs):
        self.args, self.kwargs = args, kwargs

    async def replay_workflow(self, history):
        version = os.environ["SDK_VERSION"]
        index = os.environ["RUN_INDEX"]
        evidence = Path(os.environ.get("EVIDENCE_DIR", "evidence"))
        folder = evidence / "histories" / version
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"run-{int(index):03d}-{history.workflow_id}.json"
        data = history.to_json().encode("utf-8")
        # Capture before interpreting or replaying the recorded history.
        with path.open("xb") as fp:
            fp.write(data)
        digest = hashlib.sha256(data).hexdigest()
        append_record({"phase": "history_capture", "sdk": version,
                       "iteration": int(index), "workflow_id": history.workflow_id,
                       "event_count": len(history.events),
                       "file": str(path), "sha256": digest})
        first_error = None
        for pass_number in (1, 2):
            try:
                await Replayer(*self.args, **self.kwargs).replay_workflow(history)
                status, error = "PASS", None
            except Exception as exc:
                status, error = "FAIL", repr(exc)
                if first_error is None:
                    first_error = exc
            append_record({"phase": "same_version_replay", "sdk": version,
                           "iteration": int(index), "repeat": pass_number,
                           "history_sha256": digest, "status": status,
                           "error": error})
        if first_error is not None:
            raise first_error


async def generate(repeats, cli_path):
    original.new_worker = new_worker
    original.Replayer = HistoryCapturingReplayer
    version = os.environ["SDK_VERSION"]
    kwargs = {"dev_server_existing_path": cli_path} if cli_path else {}
    async with await WorkflowEnvironment.start_local(**kwargs) as env:
        for i in range(1, repeats + 1):
            os.environ["RUN_INDEX"] = str(i)
            try:
                await original.test_workflow_concurrent_local_activity_replay(env.client)
                status, error = "PASS", None
            except Exception as exc:
                status, error = "FAIL", repr(exc)
                print("ORIGINAL_TRACEBACK", traceback.format_exc(), flush=True)
            append_record({"phase": "original_test", "sdk": version,
                           "iteration": i, "status": status, "error": error})


async def replay_saved(source_dir):
    version = os.environ["SDK_VERSION"]
    files = sorted(Path(source_dir).glob("*.json"))
    if not files:
        raise RuntimeError("Missing saved histories: " + source_dir)
    for path in files:
        payload = path.read_bytes()
        sha = hashlib.sha256(payload).hexdigest()
        workflow_id = path.stem.split("-", 2)[2]
        history = WorkflowHistory.from_json(workflow_id, payload.decode("utf-8"))
        for repeat in (1, 2):
            try:
                await Replayer(workflows=[original.ConcurrentLocalActivityReplayWorkflow]).replay_workflow(history)
                status, error = "PASS", None
            except Exception as exc:
                status, error = "FAIL", repr(exc)
                print("CROSS_REPLAY_TRACEBACK", traceback.format_exc(), flush=True)
            append_record({"phase": "cross_version_replay", "from": path.parent.name,
                           "sdk": version, "history_sha256": sha,
                           "file": str(path), "repeat": repeat, "status": status,
                           "error": error})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["generate", "replay"], required=True)
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--server-cli", default=os.getenv("TEMPORAL_CLI_PATH"))
    parser.add_argument("--source-dir")
    args = parser.parse_args()
    if args.mode == "generate":
        asyncio.run(generate(args.repeats, args.server_cli))
    else:
        if not args.source_dir:
            parser.error("--source-dir required for replay")
        asyncio.run(replay_saved(args.source_dir))


if __name__ == "__main__":
    main()
