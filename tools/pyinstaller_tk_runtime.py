"""Point bundled tkinter at manually collected Tcl/Tk script libraries."""

import os
from pathlib import Path
import sys


bundle_root = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
os.environ['TCL_LIBRARY'] = str(bundle_root / '_tcl_data')
os.environ['TK_LIBRARY'] = str(bundle_root / '_tk_data')
