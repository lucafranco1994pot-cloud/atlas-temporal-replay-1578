"""Original code from temporalio/sdk-python issue #1578.

The code below the import block is copied without edits. `new_worker` is
provided at runtime by the runner as the original project test fixture.
Source: https://github.com/temporalio/sdk-python/issues/1578
"""
import asyncio
import uuid
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Replayer


@activity.defn
async def local_activity_slow(index: int) -> None:
    if index % 2 == 0:
        await asyncio.sleep(0.05)


@activity.defn
async def local_activity_fast(index: int) -> None:
    return None


@activity.defn
async def local_activity_gate() -> None:
    await asyncio.sleep(0.05)


@workflow.defn
class ConcurrentLocalActivityReplayWorkflow:
    """Workflow that runs two concurrent coroutines with local activities.

    This reproduces a replay nondeterminism bug: during first execution,
    local activities take real time, creating a deterministic interleaving.
    During replay, all local activities return instantly from markers, which
    can reorder coroutine scheduling and produce a different command sequence.
    """

    @workflow.run
    async def run(self) -> list[int]:
        async def lifecycle_a(index: int) -> int:
            await workflow.execute_local_activity(
                local_activity_slow,
                args=[index * 2],
                start_to_close_timeout=timedelta(seconds=5),
            )
            await workflow.execute_local_activity(
                local_activity_fast,
                args=[index * 2],
                start_to_close_timeout=timedelta(seconds=5),
            )
            return index * 2

        async def lifecycle_b(index: int) -> int:
            await workflow.execute_local_activity(
                local_activity_gate,
                start_to_close_timeout=timedelta(seconds=5),
            )
            await workflow.execute_local_activity(
                local_activity_slow,
                args=[index * 2 + 1],
                start_to_close_timeout=timedelta(seconds=5),
            )
            await workflow.execute_local_activity(
                local_activity_fast,
                args=[index * 2 + 1],
                start_to_close_timeout=timedelta(seconds=5),
            )
            return index * 2 + 1

        results: list[int] = []
        for index in range(20):
            results.extend(await asyncio.gather(lifecycle_a(index), lifecycle_b(index)))
        return results


async def test_workflow_concurrent_local_activity_replay(client: Client):
    """Test that concurrent local activities replay deterministically.

    Runs a workflow with two concurrent coroutines that each issue multiple
    local activities, then replays the history. Without the fix, replay
    fails with NondeterminismError because the local activity command order
    diverges from the recorded marker order.
    """
    async with new_worker(
        client,
        ConcurrentLocalActivityReplayWorkflow,
        activities=[local_activity_slow, local_activity_fast, local_activity_gate],
    ) as worker:
        handle = await client.start_workflow(
            ConcurrentLocalActivityReplayWorkflow.run,
            id=f"workflow-{uuid.uuid4()}",
            task_queue=worker.task_queue,
        )
        expected = [v for i in range(20) for v in (i * 2, i * 2 + 1)]
        assert await handle.result() == expected

        history = await handle.fetch_history()

    await Replayer(
        workflows=[ConcurrentLocalActivityReplayWorkflow],
    ).replay_workflow(history)
