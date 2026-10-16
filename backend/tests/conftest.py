import os
import sys

# Backend modules import each other as top-level modules (as uvicorn runs them).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
