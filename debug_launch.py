import tkinter as tk
import traceback
import sys

sys.path.insert(0, '.')

try:
    from oternos.__main__ import main
    main()
except Exception as e:
    traceback.print_exc()
    input('press enter to close')
