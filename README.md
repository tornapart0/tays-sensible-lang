# Tay's Sensible Lang

Tay's Sensible Lang combines Python expressions, functions, imports and optional type
annotations with Java-style braces. It translates into Python so you can use
pandas, Matplotlib, and other Python libraries directly. The language runs on your
computer; the included ESP32-S3 firmware handles hardware commands over USB.

The robot-focused language feature is a fixed-cadence block:

```text
from mylang.robot import Robot

with Robot() as robot {
    every 100 ms for 2 s {
        robot.servo(10, 90)
        print(robot.read())
    }
}
```

`Robot()` is simulation. Real hardware requires an explicit serial port. Servo
angles are commands, not measurements. Default GPIO 10 here is an example.

## Summer biosensor cleaning

The summer TAC-cleaning functions are built in: non-wear correction, gap
imputation, jumps and flat-artifact correction, peak/rate/noise features, marked
graphs and Excel export. See [the biosensor guide](docs/BIOSENSOR.md).

```sh
python3 tools/setup.py
.venv/bin/python interpreter.py examples/biosensor_clean.mylang
```

This uses the included synthetic demo and saves a workbook, CSVs and graphs to
`artifacts/biosensor/`. For your own data, add CSV/XLSX paths after the script name.
In VS Code, use **MyLang: biosensor cleaning and graphs**.

The examples use camelCase names and braces on separate lines, following your
APCSA code. `else if`, `&&`, and `||` work alongside Python's `elif`, `and`, and
`or`. Code comments and explanatory docstrings have been removed.

## Start in VS Code

Open this folder, then `examples/robot_plot.mylang`. Set up the local environment with `python3 tools/setup.py` on a new computer. Choose **Terminal → Run Task → MyLang: robot
simulation and graph**, or run in the terminal:

```sh
.venv/bin/python interpreter.py examples/robot_plot.mylang
```

This runs a two-second simulated drive, writes `artifacts/robot_log.csv`, and
saves `artifacts/robot_plot.png`. Open the PNG in VS Code to see the graph.
**Terminal → Run Build Task** runs the currently selected `.mylang` file.
The tasks menu also includes servo simulation, CSV plotting, syntax checks,
tests, and environment setup.

On a new computer with Python 3.10 or later:

```sh
python3 tools/setup.py
```

On Windows, use `py tools/setup.py`. The tasks select `.venv/Scripts/python.exe`
on Windows. No VS Code Python extension is required to run the tasks. After
setup, you can activate the environment to use the shorter `mylang` command:

```sh
source .venv/bin/activate
mylang examples/fizzbuzz.mylang
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Syntax tour

```text
import math

name = "Taylan"
values = [1, 2, 3]
settings = {"speed": 0.25, "enabled": true}

def square(value: float) -> float {
    return value * value
}

for value in values {
    if value > 1 {
        print(name, square(value))
    } else {
        print("Small value")
    }
}

repeat 3 { print("Hello") }
every 100 ms for 1 s { print("Sampling") }
```

Supported: functions, classes, lists, dictionaries, indexing, imports, normal
Python operators, loops, `break` / `continue`, context managers, and exceptions.
Use `else if` or `elif`; `&&` / `||` also work alongside `and` / `or`. Use `true`, `false`, `null` or Python's spellings.
`#` and `//` introduce comments. `!` means `not`; `!=` means unequal.
Since `//` is a comment, use `math.floor(a / b)` for floor division.
Semicolons are optional. Braces are required for blocks; indentation is for
readability. List and dictionary expressions can span lines. In a block header,
put a dictionary/set literal inside parentheses to distinguish it from a block.
Formatted strings use Python expressions inside their interpolation braces.
Names beginning with `_mylang_` are reserved for generated code.

`repeat expression { ... }` executes `range(expression)` iterations. `every`
accepts numeric literals with `ms` or `s`, starts immediately, and skips missed
ticks. It is a best-effort desktop timer, not a hard real-time controller.

## Hardware: flash once, then write MyLang

Read **firmware/README.md** for board selection, wiring, pin restrictions, and
watchdog behavior. Upload `firmware/robot_bridge/robot_bridge.ino` with the
Arduino IDE and Espressif's 3.x board package. Close the Serial Monitor.

Find available ports:

```sh
.venv/bin/python -m serial.tools.list_ports
```

Run with YOUR port and YOUR six motor GPIOs:

```sh
.venv/bin/python interpreter.py examples/robot_plot.mylang --port /dev/cu.usbmodemYOURPORT --left 4 5 6 --right 7 8 9
```

The pin tuples are `(PWM, IN1, IN2)` for each side of a compatible dual H-bridge.
Those numbers are examples, not an assertion about your wiring. Matching motor
configuration can be reused across connections; reset the board to change it.
Your motor driver has not been specified, so check its interface before wiring.

### Robot API

| Method | Meaning |
|---|---|
| `Robot()` | Simulation |
| `Robot(port="...")` | Physical ESP32-S3 running the bridge firmware |
| `configureMotors(left=(4,5,6), right=(7,8,9))` | Assign the two motor PWM/direction pin sets |
| `drive(left, right)` | Command each motor from -1 to 1; refresh while moving |
| `move(left, right, seconds)` | Refresh motor commands for a duration, then stop |
| `servo(pin, angle, min_us=1000, max_us=2000)` | 50Hz positional servo pulse; angle 0–180 |
| `pwm(pin, duty)` | 20kHz output with duty 0–1 |
| `digitalWrite(pin, value)` | Set an output to 0 or 1 |
| `digitalRead(pin, pullup=false)` | Read a digital input |
| `analogRead(pin)` | Read ADC1 raw value; pins 1–10 excluding 3 |
| `read()` | Board uptime and commanded motor power; synthetic ADC in simulation |
| `release(pin)` | Free a GPIO/PWM/servo pin for another role |
| `stop()` | Clear all outputs, including servo pulses |

The firmware watchdog clears outputs after 500ms without an output command.
Use timed loops with intervals around 100ms. Servo pulses must be refreshed too.
Stopping servo pulses does not guarantee holding torque. The simulator models
commands and synthetic ADC samples; it does not model robot physics or wiring.
On real hardware, `read()["sensor_raw"]` is null: append
`sample["sensor_raw"] = robot.analogRead(your_adc_pin)` when logging a real sensor, or pass `--adc-pin 1` to the example (choose your actual ADC GPIO).

## pandas and Matplotlib

Import them normally; calls, keyword arguments, and DataFrames work directly:

```text
import pandas as pd
import matplotlib.pyplot as plt

frame = pd.read_csv("artifacts/robot_log.csv")
axis = frame.plot(x="time_s", y="sensor_raw")
axis.set_title("Sensor samples")
plt.show()
```

The provided examples use the non-interactive `Agg` backend to save PNGs reliably.
For interactive windows, omit `matplotlib.use("Agg")` and call `plt.show()`.
Plot any CSV with named columns:

```sh
.venv/bin/python interpreter.py examples/graph_csv.mylang --csv your.csv --x time --y distance
```

## Editor highlighting and snippets

`editor/` contains a local VS Code extension with highlighting, brace indentation,
and `every` / `robot` snippets. The packaged extension is `mylang-syntax.vsix`.
In VS Code's Extensions view, choose **… → Install from VSIX** and select it.
This is a basic grammar, not a language server: autocomplete and type checking
for imported Python libraries are not implemented.

## Check and develop the language

```sh
.venv/bin/python interpreter.py --check examples/robot_plot.mylang
.venv/bin/python interpreter.py --emit artifacts/generated.py examples/robot_plot.mylang
.venv/bin/python -m unittest discover -s tests -v
```

`--check` parses without running imports or hardware commands. Runtime errors
point to the original MyLang statement's line. `--max-steps 10000` optionally
limits executed MyLang lines; this does not time-limit imported library code.
Programs have full Python access and should be treated like Python scripts.

- `mylang/compiler.py`: token-aware brace translation and syntax features.
- `interpreter.py`: command-line execution and source-line errors.
- `mylang/timing.py`: desktop cadence scheduling.
- `mylang/robot.py`: simulated and real hardware APIs.
- `mylang/biosensor.py`: your summer TAC cleaning, plotting and export functions.
- `firmware/robot_bridge/robot_bridge.ino`: ESP32-S3 implementation.
- `learning/original_interpreter.py`: the earlier small interpreter, kept for learning.

`requirements-lock.txt` records the dependencies tested on this computer with
Python 3.14. For other Python versions, use `tools/setup.py` so pip can resolve
compatible versions. Tests cover FizzBuzz, source translation, timing, cleanup,
pin validation and simulated serial errors. The ESP32-S3 firmware also compiled with Arduino-ESP32 3.3.12 and native USB CDC enabled; see `firmware/VALIDATION.md`. Actual wiring and motor behavior require testing on your board.

## Language-card demo

Run `examples/fizzbuzz.mylang` and `examples/robot_plot.mylang`, then take a
screenshot with the source beside its output or graph. The original design
choice to explain is timed sampling blocks combined with direct Python-library
access. The README and runnable examples give you a starting point for your demo.

References: [Language card](https://crescent.hackclub.com/guides/language),
[Espressif LEDC](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html),
[S3 GPIO](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/api-reference/peripherals/gpio.html),
[pandas plotting](https://pandas.pydata.org/docs/getting_started/intro_tutorials/04_plotting.html),
[pySerial](https://pyserial.readthedocs.io/en/stable/shortintro.html).

Optional firmware behavior check (requires a native C++ compiler):

```sh
.venv/bin/python tools/check_firmware_logic.py
```

This checks the actual sketch's logic with mock GPIO/serial, including the
500ms watchdog, output clearing, pin conflicts and motor direction. It does
not validate electrical wiring or the ESP32 peripherals themselves.
