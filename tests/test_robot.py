import json
import unittest
from unittest.mock import patch
from mylang.robot import Robot, RobotError

class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.commands = []
        self.closed = False
        self.bad_response = None

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self.commands.append(data.decode().strip())
        return len(data)

    def readline(self, size):
        if self.bad_response is not None:
            return self.bad_response
        command = self.commands[-1]
        response = {'ok': True}
        if command == 'INFO':
            response.update(protocol=1, motors_ready=False)
        if command == 'READ':
            response.update(time_s=1, left=0, right=0, sensor_raw=None)
        if command.startswith(('DIGITAL', 'ANALOG')):
            response['value'] = 123 if command.startswith('ANALOG') else 1
        return (json.dumps(response) + '\n').encode()

    def close(self):
        self.closed = True

class RobotTests(unittest.TestCase):
    def test_simulation_motors(self):
        with Robot() as robot:
            with self.assertRaises(RobotError):
                robot.drive(0.2, 0.2)
            robot.configure_motors((4, 5, 6), (7, 8, 9))
            robot.drive(0.3, -0.4)
            self.assertEqual(robot.read()['left'], 0.3)
            with self.assertRaises(ValueError):
                robot.digital_write(4, 1)
            for value in [2, float('nan'), True]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    robot.drive(value, 0)
        self.assertTrue(robot.closed)
        self.assertEqual(robot.left, 0)

    def test_pin_roles_watchdog(self):
        with Robot() as robot:
            robot.servo(10, 90)
            robot.pwm(11, 0.5)
            with self.assertRaises(ValueError):
                robot.digital_write(10, 1)
            for pin in [0, 3, 19, 20, 26, 37, 43, 48, -1, 99]:
                with self.subTest(pin=pin), self.assertRaises(ValueError):
                    robot.digital_write(pin, 1)
            robot.last_drive -= 1
            robot.read()
            self.assertEqual(robot.pins[10][1], 0)
            self.assertEqual(robot.pins[11][1], 0)
            robot.release(10)
            robot.digital_write(10, 1)

    def test_channel_limits(self):
        with Robot() as robot:
            for pin in [4, 5, 6, 7]:
                robot.servo(pin, 90)
            with self.assertRaises(ValueError):
                robot.servo(8, 90)
            robot.release(4)
            robot.servo(8, 90)

    def test_serial_protocol(self):
        with patch('serial.Serial', FakeSerial), patch('mylang.robot.time.sleep'):
            with Robot(port='FAKE') as robot:
                robot.configure_motors((4, 5, 6), (7, 8, 9))
                robot.drive(0.5, -0.5)
                robot.servo(10, 90)
                self.assertEqual(robot.analog_read(1), 123)
                self.assertIsNone(robot.read()['sensor_raw'])
                connection = robot.connection
            self.assertIn('DRIVE 128 -128', connection.commands)
            self.assertIn('SERVO 10 1500', connection.commands)
            self.assertEqual(connection.commands[-1], 'STOP')
            self.assertTrue(connection.closed)

    def test_reconnect_reuses_reported_motor_pins(self):
        class ConfiguredSerial(FakeSerial):
            def readline(self, size):
                if self.commands[-1] == 'INFO':
                    return b'{"ok":true,"protocol":1,"motors_ready":true,"motor_pins":[4,5,6,7,8,9]}\n'
                return super().readline(size)

        with patch('serial.Serial', ConfiguredSerial), patch('mylang.robot.time.sleep'):
            with Robot(port='FAKE') as robot:
                robot.configure_motors((4, 5, 6), (7, 8, 9))
                self.assertEqual(robot.motor_pins, {4, 5, 6, 7, 8, 9})
                with self.assertRaises(ValueError):
                    robot.configure_motors((10, 11, 12), (13, 14, 15))
                with self.assertRaises(ValueError):
                    robot.servo(4, 90)

    def test_serial_failure_stops(self):
        for response in [b'', b'{bad}\n', b'[]\n', b'{"ok":true}', b'{"ok":false,"error":"bad GPIO"}\n']:
            with self.subTest(response=response), patch('serial.Serial', FakeSerial), patch('mylang.robot.time.sleep'):
                robot = Robot(port='FAKE')
                robot.connection.bad_response = response
                with self.assertRaises(RobotError):
                    robot.read()
                self.assertTrue(robot.closed)
                self.assertEqual(robot.connection.commands[-1], 'STOP')

    def test_interruption_stops(self):
        with Robot() as robot:
            robot.configure_motors((4, 5, 6), (7, 8, 9))
            with patch('mylang.robot.time.sleep', side_effect=KeyboardInterrupt):
                with self.assertRaises(KeyboardInterrupt):
                    robot.move(0.2, 0.2, 1)
            self.assertEqual(robot.left, 0)
