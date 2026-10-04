# Validation — October 3, 2026

The firmware compiled successfully with Arduino-ESP32 **3.3.12** for:

```text
esp32:esp32:esp32s3:CDCOnBoot=cdc
```

Compile command (after installing Arduino CLI and the Espressif board package):

```sh
arduino-cli compile --fqbn esp32:esp32:esp32s3:CDCOnBoot=cdc --warnings all firmware/robot_bridge
```

Result: 335529 bytes of program storage and 23312 bytes of global variables.
The compiler reported no warnings. This validates the S3 build with native
USB CDC enabled, not your specific board's flash/PSRAM settings or wiring.
No firmware was uploaded and no physical ESP32 was connected during validation.

The native mock-hardware check also passed: PWM/servo timer separation, motor
control, unavailable GPIO rejection, role conflicts, output clearing and the
500ms watchdog. The Python suite covers language execution, plotting, timing,
simulation and serial-protocol behavior, including timeout handling.
