"""
Backward-compatibility alias for email_notifier.
Core implementation has moved to `hackingupdate.email_notifier`.
"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import hackingupdate.email_notifier as _real_module

sys.modules[__name__] = _real_module

if __name__ == "__main__":
    if hasattr(_real_module, "main"):
        _real_module.main()
