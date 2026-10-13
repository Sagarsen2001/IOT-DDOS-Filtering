"""
tests/conftest.py
=================
Shared pytest fixtures and path setup.
Ensures the project root is always on sys.path regardless of
where pytest is invoked from.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
