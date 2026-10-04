import json
import math
import threading
import time

AVAILABLE_PINS = (set(range(1, 19)) - {3}) | set(range(38, 43)) | {47}

class RobotError(Exception):
    pass

def speed(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Motor speed must be a number from -1 to 1')
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError('Motor speed must be from -1 to 1')
    return float(value)

class Robot:

    def __init__(self, port=None, baudrate=115200, timeout=1.0):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('timeout must be a positive finite number')
        self.simulated = port is None
        self.closed = False
        self.left = self.right = 0.0
        self.started = time.monotonic()
        self.last_drive = self.started
        self.pins = {}
        self.motor_pins = set()
        self.motor_configuration = ()
        self.timeout = timeout
        self.lock = threading.Lock()
        self.connection = None
        if not self.simulated:
            import serial
            try:
                self.connection = serial.Serial(port, baudrate, timeout=timeout,
                                                write_timeout=timeout)
                time.sleep(2)
                self.connection.reset_input_buffer()
                info = self._request('INFO')
                if info.get('protocol') != 1:
                    raise RobotError('Unsupported firmware protocol')
                self.motors_ready = info.get('motors_ready', False)
                if self.motors_ready:
                    configuration = info.get('motor_pins', [])
                    if len(configuration) != 6:
                        raise RobotError('Firmware did not report configured motor pins')
                    self.motor_configuration = tuple(configuration)
                    self.motor_pins = set(configuration)
                self.stop()
            except BaseException:
                if self.connection:
                    self.connection.close()
                raise
        else:
            self.motors_ready = False

    def _ensure_open(self):
        if self.closed:
            raise RobotError('Robot connection is closed')

    def _request(self, command):
        self._ensure_open()
        with self.lock:
            try:
                self.connection.write((command + '\n').encode('ascii'))
                raw = self.connection.readline(1024)
                if not raw.endswith(b'\n'):
                    raise RobotError('ESP32 response timed out or was incomplete')
                response = json.loads(raw)
                if not isinstance(response, dict) or response.get('ok') is not True:
                    message = response.get('error', 'invalid response') if isinstance(response, dict) else 'invalid response'
                    raise RobotError(f'ESP32: {message}')
                return response
            except Exception as error:

                try:
                    self.connection.write(b'STOP\n')
                except Exception:
                    pass
                self.connection.close()
                self.closed = True
                raise RobotError(f'Serial command failed: {error}') from error

    def drive(self, left, right):
        self._ensure_open()
        left, right = speed(left), speed(right)
        if not self.motors_ready:
            raise RobotError('Configure motor pins in firmware before driving')
        if not self.simulated:
            self._request(f'DRIVE {round(left * 255)} {round(right * 255)}')
        self.left, self.right = left, right
        self.last_drive = time.monotonic()

    def stop(self):
        self._ensure_open()
        if not self.simulated:
            self._request('STOP')
        self.left = self.right = 0.0
        self._clear_outputs()

    def _clear_outputs(self):
        for pin, (mode, value) in list(self.pins.items()):
            if mode != 'input':
                self.pins[pin] = (mode, 0)

    def _pin(self, pin):

        if type(pin) is not int or pin not in AVAILABLE_PINS:
            raise ValueError('Pin is unavailable in the default ESP32-S3 profile')
        if pin in self.motor_pins:
            raise ValueError('Pin is reserved for a configured motor')
        return pin

    def _claim(self, pin, mode):
        self._ensure_open()
        self._pin(pin)
        if pin in self.pins and self.pins[pin][0] != mode:
            raise ValueError('Pin already has another role; release it first')
        if pin not in self.pins and mode in ('pwm', 'servo'):
            count = sum(role == mode for role, _ in self.pins.values())
            if count >= {'pwm': 2, 'servo': 4}[mode]:
                raise ValueError('No free PWM channels for this role')

    def configure_motors(self, left, right):

        self._ensure_open()
        if len(left) != 3 or len(right) != 3:
            raise ValueError('Each motor needs (PWM, IN1, IN2) pins')
        pins = [*left, *right]
        if self.motors_ready:
            if tuple(pins) == self.motor_configuration:
                self.stop()
                return
            raise ValueError('Motors already configured; reset board to change pins')
        for pin in pins:
            self._pin(pin)
            if pin in self.pins:
                raise ValueError('Motor pin already in use')
        if len(set(pins)) != 6:
            raise ValueError('All six motor pins must be different')
        if not self.simulated:
            self._request('MOTORS ' + ' '.join(map(str, pins)))
        self.motor_pins = set(pins)
        self.motor_configuration = tuple(pins)
        self.motors_ready = True

    def digital_write(self, pin, value):
        self._claim(pin, 'digital')
        if value not in (0, 1, False, True):
            raise ValueError('Digital output must be 0 or 1')
        if not self.simulated:
            self._request(f'WRITE {pin} {int(value)}')
        self.pins[pin] = ('digital', int(value))
        self.last_drive = time.monotonic()

    def digital_read(self, pin, pullup=False):
        self._claim(pin, 'input')
        if not self.simulated:
            result = self._request(f'DIGITAL {pin} {int(bool(pullup))}')['value']
        else:
            result = int(bool(pullup))
        self.pins[pin] = ('input', result)
        return result

    def analog_read(self, pin):
        self._claim(pin, 'input')
        if not 1 <= pin <= 10:
            raise ValueError('ADC sampling supports ADC1 pins 1–10, excluding 3')
        if not self.simulated:
            result = self._request(f'ANALOG {pin}')['value']
        else:
            result = self.read()['sensor_raw']
        self.pins[pin] = ('input', result)
        return result

    def pwm(self, pin, duty):
        self._claim(pin, 'pwm')
        if type(duty) not in (int, float) or not math.isfinite(duty) or not 0 <= duty <= 1:
            raise ValueError('PWM duty must be from 0 to 1')
        if not self.simulated:
            self._request(f'PWM {pin} {round(duty * 255)}')
        self.pins[pin] = ('pwm', duty)
        self.last_drive = time.monotonic()

    def servo(self, pin, angle, min_us=1000, max_us=2000):

        self._claim(pin, 'servo')
        if type(angle) not in (int, float) or not math.isfinite(angle) or not 0 <= angle <= 180:
            raise ValueError('Servo angle must be from 0 to 180')
        if type(min_us) is not int or type(max_us) is not int or not 500 <= min_us < max_us <= 2500:
            raise ValueError('Servo pulse limits must be integers between 500 and 2500 us')
        pulse = round(min_us + (max_us - min_us) * angle / 180)
        if not self.simulated:
            self._request(f'SERVO {pin} {pulse}')
        self.pins[pin] = ('servo', angle)
        self.last_drive = time.monotonic()

    def release(self, pin):
        self._ensure_open()
        self._pin(pin)
        if not self.simulated:
            self._request(f'RELEASE {pin}')
        self.pins.pop(pin, None)

    def move(self, left, right, seconds):

        speed(left)
        speed(right)
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('seconds must be a nonnegative finite number')
        deadline = time.monotonic() + seconds
        try:
            while time.monotonic() < deadline:
                self.drive(left, right)
                time.sleep(max(0, min(0.1, deadline - time.monotonic())))
        finally:
            if not self.closed:
                self.stop()

    def read(self):
        self._ensure_open()
        if not self.simulated:
            data = self._request('READ')
            return {key: data[key] for key in ('time_s', 'left', 'right', 'sensor_raw')}
        now = time.monotonic()
        if now - self.last_drive >= 0.5:
            self.left = self.right = 0.0
            self._clear_outputs()
        elapsed = now - self.started

        return {'time_s': elapsed, 'left': self.left, 'right': self.right,
                'sensor_raw': round(2048 + 500 * math.sin(elapsed * 3))}

    def close(self):
        if self.closed:
            return
        try:
            self.stop()
        finally:
            if self.connection:
                self.connection.close()
            self.closed = True

    configureMotors = configure_motors
    digitalWrite = digital_write
    digitalRead = digital_read
    analogRead = analog_read

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, kind, value, traceback):
        try:
            self.close()
        except Exception:
            if kind is None:
                raise

def list_ports():
    from serial.tools.list_ports import comports
    return [{'port': port.device, 'description': port.description} for port in comports()]

listPorts = list_ports
