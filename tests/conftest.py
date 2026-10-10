import sys
from pathlib import Path

# Ensure project root is always on sys.path for test discovery
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
