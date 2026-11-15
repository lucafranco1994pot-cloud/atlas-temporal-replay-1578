"""Isolated version-boundary check for SDK 1.31.0.

Replace only _shield_await (introduced after 1.30.0) with the legacy
asyncio.shield semantics, leaving the original issue #1578 code unchanged.
This is a diagnostic experiment, not a proposed production patch.
"""
import asyncio
import temporalio.worker._workflow_instance as workflow_instance


async def legacy_shield(fut):
    return await asyncio.shield(fut)


workflow_instance._shield_await = legacy_shield

import runner

runner.main()
