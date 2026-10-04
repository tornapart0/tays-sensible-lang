import os
import subprocess
import venv
from pathlib import Path

project = Path(__file__).resolve().parent.parent
environment = project / '.venv'
python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
if not python.exists():
    venv.EnvBuilder(with_pip=True).create(environment)
subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(project)], check=True)
print('Ready. Run:', python, 'interpreter.py examples/robot_plot.mylang')
