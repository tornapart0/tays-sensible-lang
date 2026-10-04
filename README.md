# Tay's Sensible Lang

I wanted a language that lets me write code the way I like. Basically Python with Java braces, plus things I use for ESP32 robots and cleaning biosensor data. It uses pandas and matplotlib because I already use those for graphs.

The code runs on your computer. The ESP32-S3 runs a small Arduino sketch and takes commands over USB. You are not uploading `.mylang` files directly to the board.

## Run it

You need Python 3.10 or newer. Open this folder in VS Code, then run:

```sh
python3 tools/setup.py
.venv/bin/python interpreter.py examples/fizzbuzz.mylang
```

On Windows, use `py tools/setup.py`, then `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

The files end in `.mylang`. Install `mylang-syntax.vsix` through **Extensions → … → Install from VSIX** if you want syntax highlighting. The VS Code tasks can also run the current file, the robot demo, and the cleaning examples.

## What the code looks like

```text
for number in range(1, 101)
{
    if number % 15 == 0
    {
        print("FizzBuzz")
    }
    else if number % 3 == 0
    {
        print("Fizz")
    }
    else if number % 5 == 0
    {
        print("Buzz")
    }
    else
    {
        print(number)
    }
}
```

Use normal Python imports, functions, classes, lists and dictionaries. `else if`, `&&`, `||`, `!`, `true`, `false` and `null` work too. Semicolons are optional. Blocks need braces.

`repeat 3 { ... }` repeats something three times. `every 100 ms for 2 s { ... }` runs a timed loop. It starts straight away and skips ticks if the computer falls behind. It is not a precise hardware timer.

## Robots

Start with the simulator:

```sh
.venv/bin/python interpreter.py examples/robot_plot.mylang
```

That makes `artifacts/robot_log.csv` and `artifacts/robot_plot.png`.

For a real robot, upload [the bridge sketch](firmware/robot_bridge/robot_bridge.ino) using Arduino IDE and the ESP32 3.x board package. [The firmware README](firmware/README.md) has the board settings and wiring details. Close Serial Monitor before running this.

```sh
.venv/bin/python -m serial.tools.list_ports
.venv/bin/python interpreter.py examples/robot_plot.mylang --port /dev/cu.usbmodemYOURPORT --left 4 5 6 --right 7 8 9
```

Replace the port and pins with yours. Each motor takes `(PWM, IN1, IN2)` for a compatible H-bridge driver. The numbers above are just examples. GPIOs are configurable, but some S3 pins are reserved or unsuitable.

There are functions for motors, servos, PWM, digital inputs and outputs, and analog inputs. `Robot()` uses simulation. `Robot(port="...")` uses the board. Look at [servo_gpio.mylang](examples/servo_gpio.mylang) for servos and [robot_plot.mylang](examples/robot_plot.mylang) for motors and logging.

Refresh output commands about every 100 ms. The firmware clears outputs after 500 ms without one. Stopping servo pulses does not mean the servo will hold its position. For a real sensor reading, give the robot example `--adc-pin` with your ADC pin.

## Biosensor cleaning and graphs

I added the TAC cleaning functions from my summer work: nonwear correction, filling gaps, correcting jumps and flat artifacts, calculating features, plotting the result, and exporting to Excel.

```sh
.venv/bin/python interpreter.py examples/biosensor_clean.mylang
```

This uses fake demo data. The workbook, cleaned CSV and graphs go in `artifacts/biosensor/`.

To use your own files:

```sh
.venv/bin/python interpreter.py examples/biosensor_clean.mylang data.csv another_file.xlsx
```

Your data needs time, TAC, temperature and motion columns. [The biosensor guide](docs/BIOSENSOR.md) explains the columns and cleaning settings. [biosensor_steps.mylang](examples/biosensor_steps.mylang) shows the individual functions if you want to change the process.

You can also import pandas and matplotlib directly, or graph a CSV like this:

```sh
.venv/bin/python interpreter.py examples/graph_csv.mylang --csv your.csv --x time --y distance
```

## Working on it

The language translation is in `mylang/compiler.py`. The runner is `interpreter.py`. Robot commands are in `mylang/robot.py`, and cleaning is in `mylang/biosensor.py`. `learning/original_interpreter.py` is the smaller interpreter I started with.

```sh
.venv/bin/python interpreter.py --check examples/robot_plot.mylang
.venv/bin/python -m unittest discover -s tests
.venv/bin/python tools/check_firmware_logic.py
```

The last command needs a C++ compiler. There are 29 passing Python tests, and the firmware compiled for the ESP32-S3 with Arduino-ESP32 3.3.12. I still need to test the actual robot hardware. [Build details](firmware/VALIDATION.md).

This translates to Python. It has Python's access to your computer, and the editor extension is basic syntax highlighting. It does not have a full autocomplete system yet.
