#!/usr/bin/env python3
"""Analyze associativity using the shared PMU workflow."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'common'))
from analyze_verification import main
if __name__ == '__main__':
    sys.argv[1:1] = ['--experiment', 'associativity']
    main()
