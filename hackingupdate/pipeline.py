"""
Pipeline orchestrator — replaces run_brief.sh with pure Python.

Executes each pipeline step in sequence, with proper error handling,
timing, and the ability to run individual steps.
"""

import sys
import time
import importlib
from pathlib import Path

from hackingupdate.config import get_logger, CACHE_DIR

logger = get_logger("pipeline")

# Ordered list of pipeline steps.
# Each tuple: (step_name, module_path_relative_to_scripts, description)
PIPELINE_STEPS = [
    ("fetch",       "fetcher",              "Fetching security feeds"),
    ("extract",     "extractor",            "Extracting and cleaning content"),
    ("fingerprint", "fingerprint_analyzer", "Generating content fingerprints"),
    ("dedupe",      "dedupe_fingerprints",  "Running deduplication engine"),
    ("rank",        "priority_ranker",      "Tagging & ranking articles"),
    ("workingset",  "build_working_set",    "Compiling working set"),
    ("db_store",    "db_manager",           "Storing findings to SQLite database"),
    ("report",      "report_generator",     "Generating Markdown daily brief"),
    ("html",        "html_generator",       "Rendering HTML brief"),
    ("teams",       "teams_notifier",       "Sending Teams notifications"),
    ("whatsapp",    "whatsapp_notifier",    "Sending WhatsApp notifications"),
    ("prune",       "prune_logs",           "Pruning old logs"),
]


def _import_step_module(module_name: str):
    """Dynamically import a script module from the scripts/ directory."""
    # Ensure scripts dir is on sys.path
    scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    # Also ensure project root is on sys.path for config imports
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    return importlib.import_module(module_name)


def clear_cache():
    """Remove all cached JSON files to start fresh."""
    if CACHE_DIR.is_dir():
        removed = 0
        for json_file in CACHE_DIR.glob("*.json"):
            json_file.unlink()
            removed += 1
        logger.info(f"Cleared {removed} cached JSON file(s) from {CACHE_DIR}")
    else:
        logger.info("No cache directory found, nothing to clear.")


def run_step(step_name: str) -> bool:
    """
    Run a single pipeline step by name.
    Returns True on success, False on failure.
    """
    # Find the step
    step_info = None
    for name, module_name, description in PIPELINE_STEPS:
        if name == step_name:
            step_info = (name, module_name, description)
            break

    if not step_info:
        logger.error(f"Unknown pipeline step: '{step_name}'. "
                      f"Available: {[s[0] for s in PIPELINE_STEPS]}")
        return False

    name, module_name, description = step_info
    return _execute_step(name, module_name, description)


def _execute_step(name: str, module_name: str, description: str) -> bool:
    """Execute a single pipeline step."""
    logger.info(f"▶ [{name}] {description}...")
    start = time.time()

    try:
        module = _import_step_module(module_name)
        if hasattr(module, "main"):
            module.main()
        else:
            logger.warning(f"Module '{module_name}' has no main() function, skipping.")
        elapsed = time.time() - start
        logger.info(f"✓ [{name}] Completed in {elapsed:.1f}s")
        return True
    except SystemExit as e:
        # Scripts call sys.exit(1) on failure — catch it
        if e.code == 0:
            elapsed = time.time() - start
            logger.info(f"✓ [{name}] Completed in {elapsed:.1f}s")
            return True
        elapsed = time.time() - start
        logger.error(f"✗ [{name}] Failed with exit code {e.code} after {elapsed:.1f}s")
        return False
    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"✗ [{name}] Error after {elapsed:.1f}s: {e}")
        return False


def run_pipeline(steps: list[str] | None = None, skip_cache_clear: bool = False):
    """
    Run the full pipeline or a subset of steps.

    Args:
        steps: Optional list of step names to run. If None, runs all steps.
        skip_cache_clear: If True, skip clearing the cache before running.
    """
    logger.info("=" * 60)
    logger.info("Starting Daily Security Briefing Pipeline")
    logger.info("=" * 60)

    pipeline_start = time.time()

    # Clear cache for fresh data (unless skipped)
    if not skip_cache_clear:
        clear_cache()

    # Determine which steps to run
    if steps:
        steps_to_run = []
        for step_name in steps:
            found = False
            for name, module_name, description in PIPELINE_STEPS:
                if name == step_name:
                    steps_to_run.append((name, module_name, description))
                    found = True
                    break
            if not found:
                logger.error(f"Unknown step: '{step_name}'. "
                              f"Available: {[s[0] for s in PIPELINE_STEPS]}")
                sys.exit(1)
    else:
        steps_to_run = PIPELINE_STEPS

    # Execute each step
    total = len(steps_to_run)
    failed = []

    for i, (name, module_name, description) in enumerate(steps_to_run, 1):
        logger.info(f"Step {i}/{total}: {description}")
        success = _execute_step(name, module_name, description)
        if not success:
            failed.append(name)
            # For notification steps, continue on failure
            if name in ("teams", "whatsapp", "prune", "db_store"):
                logger.warning(f"Non-critical step '{name}' failed, continuing...")
            else:
                logger.error(f"Critical step '{name}' failed, aborting pipeline.")
                break

    elapsed = time.time() - pipeline_start
    logger.info("=" * 60)

    if failed:
        logger.warning(f"Pipeline finished in {elapsed:.1f}s with {len(failed)} failure(s): {failed}")
    else:
        logger.info(f"Pipeline finished successfully in {elapsed:.1f}s ({total} steps)")

    logger.info("=" * 60)

    return len(failed) == 0
