import sys
import os
from pathlib import Path

# Add bundled libs to path
libs_path = str(Path(__file__).parent / "synapse" / "libs")
if libs_path not in sys.path:
    sys.path.insert(0, libs_path)

from synapse.__main__ import main

if __name__ == "__main__":
    main()
