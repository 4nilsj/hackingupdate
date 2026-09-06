"""
Backward-compatibility alias for db_manager.
Core implementation has moved to `hackingupdate.db_manager`.
"""

import sys
from pathlib import Path

_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import hackingupdate.db_manager as _real_module

sys.modules[__name__] = _real_module

if __name__ == "__main__":
    if hasattr(_real_module, "main"):
        _real_module.main()
