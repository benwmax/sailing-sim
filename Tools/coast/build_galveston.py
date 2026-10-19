"""The Texas coast's old entry point: Tools/coast/build_coast.py bakes every coast world now (Tools/coast/worlds/).

Run: Tools/venv/bin/python Tools/coast/build_galveston.py [galveston|gulf]   (the same as build_coast.py)
"""
import os
import runpy
import sys

if len(sys.argv) < 2:
    sys.argv.append("galveston")
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_coast.py"), run_name="__main__")
