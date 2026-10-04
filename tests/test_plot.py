import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from interpreter import run
from mylang.robot import Robot

class NoSensorRobot(Robot):
    def read(self):
        result = super().read()
        result['sensor_raw'] = None
        return result

class PlotTests(unittest.TestCase):
    def test_unconfigured_sensor_still_saves_graph(self):
        source = Path('examples/robot_plot.mylang').read_text()
        with tempfile.TemporaryDirectory() as directory:
            with patch('mylang.robot.Robot', NoSensorRobot), patch('interpreter.every', return_value=iter([0.0, 0.1])), contextlib.redirect_stdout(io.StringIO()):
                run(source, arguments=['--output', directory])
            frame = pd.read_csv(Path(directory) / 'robot_log.csv')
            self.assertEqual(len(frame), 2)
            self.assertTrue(frame['sensor_raw'].isna().all())
            self.assertTrue((Path(directory) / 'robot_plot.png').read_bytes().startswith(b'\x89PNG'))
