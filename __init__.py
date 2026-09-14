"""ComfyUI node that requests a full memory cleanup every N prompt runs."""

from __future__ import annotations

import math
import threading
from typing import Any

from server import PromptServer


class AnyType(str):
    """ComfyUI wildcard type used for an optional pass-through signal."""

    def __eq__(self, _other: object) -> bool:
        return True

    def __ne__(self, _other: object) -> bool:
        return False


ANY = AnyType("*")
_COUNTS: dict[str, int] = {}
_LOCK = threading.Lock()


def _workflow_key(unique_id: Any, extra_pnginfo: Any) -> str:
    """Keep counters independent between saved workflows where possible."""

    workflow_id = ""
    if isinstance(extra_pnginfo, dict):
        workflow = extra_pnginfo.get("workflow")
        if isinstance(workflow, dict):
            workflow_id = str(workflow.get("id", ""))
    return f"{workflow_id}:{unique_id}"


class GenerationIntervalCleanup:
    """Count prompt executions and request ComfyUI cleanup at an interval.

    The cleanup is requested through PromptQueue flags. ComfyUI consumes those
    flags after the current prompt has completely finished, so models are never
    unloaded while the current generation is still using them.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "every_n": (
                    "INT",
                    {
                        "default": 50,
                        "min": 1,
                        "max": 1_000_000,
                        "step": 1,
                        "tooltip": "Counts one prompt execution as one run and requests cleanup at this interval. This is not a batch-size setting.",
                    },
                ),
                "unload_models": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Unload models",
                        "label_off": "Keep models loaded",
                        "tooltip": "Requests unloading of managed models after the current prompt finishes.",
                    },
                ),
                "clear_execution_cache": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "label_on": "Clear execution cache",
                        "label_off": "Keep execution cache",
                        "tooltip": "Requests execution-cache reset, Python garbage collection, and device-cache cleanup after the current prompt finishes.",
                    },
                ),
            },
            "optional": {
                "signal": (
                    ANY,
                    {
                        "tooltip": "Optional pass-through. Connect the final IMAGE or another completion signal to count only executions that reach that stage."
                    },
                ),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = (ANY, "INT", "BOOLEAN")
    RETURN_NAMES = ("signal", "current_count", "cleaned_now")
    OUTPUT_NODE = True
    FUNCTION = "count_and_request_cleanup"
    CATEGORY = "Memory Management"
    DESCRIPTION = (
        "Counts prompt executions and asks ComfyUI to unload models and clear "
        "memory after the configured interval. It does not create batches or "
        "submit additional prompts."
    )

    @classmethod
    def IS_CHANGED(cls, **_kwargs):
        # This output node must be visited once for every submitted prompt.
        return math.nan

    def count_and_request_cleanup(
        self,
        every_n: int,
        unload_models: bool,
        clear_execution_cache: bool,
        signal: Any = None,
        unique_id: Any = None,
        extra_pnginfo: Any = None,
    ):
        interval = max(1, int(every_n))
        key = _workflow_key(unique_id, extra_pnginfo)

        with _LOCK:
            current = _COUNTS.get(key, 0) + 1
            cleaned_now = current >= interval
            _COUNTS[key] = 0 if cleaned_now else current

        if cleaned_now:
            queue = PromptServer.instance.prompt_queue
            if clear_execution_cache:
                queue.set_flag("free_memory", True)
                # free_memory defaults to unloading models in ComfyUI. Set the
                # explicit value so the widget remains authoritative.
                queue.set_flag("unload_models", bool(unload_models))
            elif unload_models:
                queue.set_flag("unload_models", True)

            status = (
                f"{interval}/{interval}: cleanup requested after this prompt. "
                "The next run starts again at 1."
            )
            print(f"[Generation Interval Cleanup] {status}")
        else:
            status = f"{current}/{interval} ({interval - current} remaining)"

        return {
            "ui": {"text": [status]},
            "result": (signal, current, cleaned_now),
        }


NODE_CLASS_MAPPINGS = {
    "GenerationIntervalCleanup": GenerationIntervalCleanup,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GenerationIntervalCleanup": "🧹 Generation Interval Cleanup",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
