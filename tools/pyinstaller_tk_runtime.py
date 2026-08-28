"""Point bundled tkinter at manually collected Tcl/Tk script libraries."""

import os
from pathlib import Path
import sys


bundle_root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
tcl_library = bundle_root / '_tcl_data'
tk_library = bundle_root / '_tk_data'

os.environ['TCL_LIBRARY'] = str(tcl_library)
os.environ['TK_LIBRARY'] = str(tk_library)
