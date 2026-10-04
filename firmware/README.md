# ESP32-S3 bridge firmware

The language runs on your computer. This sketch runs on the ESP32-S3 and handles
GPIO, servo pulses and dual H-bridge motors over USB serial. pandas and Matplotlib
run on your computer, not on the microcontroller. This is not standalone robot
code: keep the computer connected while controlling the robot.

## Flash with Arduino IDE

1. Install Arduino IDE and the **esp32 by Espressif Systems** board package, 3.x.
   Official instructions: https://docs.espressif.com/projects/arduino-esp32/en/latest/installing.html
2. Open `robot_bridge/robot_bridge.ino`.
3. Select your exact S3 board (generic fallback: **ESP32S3 Dev Module**).
4. Match flash/PSRAM settings to your board. For native USB, enable
   **USB CDC On Boot**. Choose the board's USB serial port.
5. Upload. Close the Serial Monitor before running a MyLang program.

No GPIO is driven at startup. Select pins in your MyLang program at runtime.
The default usable profile is 1–18 except 3, 38–42, and 47. It excludes USB
19/20, flash/PSRAM 26–37, strapping pins, default UART pins, and the usual RGB LED
pin. Some boards have further onboard pin uses: check YOUR board schematic.
The exact same profile is validated in `mylang/robot.py` and `usable()` in the
sketch. Update both if your board allows a different pin. ADC sampling is limited
to ADC1 pins 1–10, excluding 3.

Pin roles cannot overlap. `release(pin)` frees a GPIO/PWM/servo role. Motors are
configured once per board boot; reset the ESP32 to change motor pins. Disconnect
and reconnect the host after resetting. Do not run other serial tools concurrently.

## Wiring and behavior

- The motor API expects a dual H-bridge with **PWM, IN1, IN2 per motor**.
  Use a driver compatible with this interface. An L298-style driver requires
  removing enable jumpers for PWM control; other drivers may need a standby pin
  held high. Use `digital_write()` for that pin and refresh it during motion.
- GPIO signals are 3.3V. Motors need a motor driver and a suitable motor supply.
  Servos need a supply appropriate to their rating, with a common ground to ESP32.
  Do not power motors or a servo directly from a GPIO.
- `servo(pin, angle)` generates a 50Hz signal with a default 1000–2000us range.
  Angle is an approximate command, not a measured angle. Calibrate from the
  servo datasheet using `min_us` / `max_us`; continuous-rotation servos interpret
  the pulses as speed rather than position.
- `pwm(pin, duty)` is 20kHz, 8-bit. Two generic PWM outputs and four servo outputs
  are available in addition to two motor PWM outputs. The fixed allocation
  prevents shared LEDC timers from changing another output's frequency.
- `stop()` clears every output, including servo pulses and generic PWM.
  **Servos stop receiving pulses; holding torque is not guaranteed.**
- If no output command arrives for 500ms, firmware clears all outputs. Refresh
  output commands with `every 100 ms ...`, including servo commands. Reading
  sensors alone does not refresh the watchdog. `move()` refreshes motors and
  stops at the end. This software watchdog is not a physical emergency stop.
- `read()` reports commanded motor power, not measured wheel speed. Its
  `sensor_raw` is null on hardware. Call `analog_read(pin)` to sample a real ADC.
  No encoder, distance, battery or temperature sensor driver is included yet.

## Protocol

115200 baud; one ASCII command per line; one JSON response per command.
`INFO`, `STOP`, `READ`, `MOTORS lpwm lin1 lin2 rpwm rin1 rin2`,
`DRIVE left right` (-255..255), `WRITE pin value`, `DIGITAL pin pullup`,
`ANALOG pin`, `PWM pin duty` (0..255), `SERVO pin pulse_us`, `RELEASE pin`.
Success contains `"ok":true`; failure contains `"ok":false,"error":"..."`.
The host fails closed on timeouts/malformed responses and never retries a drive.

References:
- https://docs.espressif.com/projects/arduino-esp32/en/latest/api/ledc.html
- https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/api-reference/peripherals/gpio.html
