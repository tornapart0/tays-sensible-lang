import os
import shutil
import subprocess
from pathlib import Path

project = Path(__file__).resolve().parent.parent
compiler = shutil.which('clang++') or shutil.which('g++')
if not compiler:
    raise SystemExit('Install a C++ compiler to run the optional firmware logic check')
fixtures = project / 'tests' / 'firmware_mock'
artifacts = project / 'artifacts'
artifacts.mkdir(exist_ok=True)
binary = artifacts / ('firmware-check.exe' if os.name == 'nt' else 'firmware-check')
subprocess.run([compiler, '-std=c++17', '-I', str(fixtures),
                str(fixtures / 'check.cpp'), '-o', str(binary)], check=True)
subprocess.run([str(binary)], check=True)
