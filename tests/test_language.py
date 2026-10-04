import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch
from interpreter import run
from mylang.compiler import LanguageError, translate

class LanguageTests(unittest.TestCase):
    def test_original_example(self):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            run(Path('examples/main.mylang').read_text())
        self.assertIn('Your score: 15', capture.getvalue())

    def test_fizzbuzz(self):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):
            run(Path('examples/fizzbuzz.mylang').read_text())
        lines = capture.getvalue().splitlines()
        self.assertEqual(len(lines), 100)
        self.assertEqual(lines[:5], ['1', '2', 'Fizz', '4', 'Buzz'])
        self.assertEqual(lines[14], 'FizzBuzz')

    def test_functions_and_collections(self):
        result = run('''
import math
def square(x: float) -> float {
    return x * x
}
values = []
repeat 3 { values.append(square(2)) }
record = {"true": true, "values": values}
result = math.sqrt(record["values"][0])
''')
        self.assertEqual(result['result'], 2)
        self.assertEqual(result['record'], {'true': True, 'values': [4, 4, 4]})

    def test_strings_comments_nested_blocks(self):
        result = run('''
s = "{ true // # }"
// ignore this comment
if true {
    if false {} else { s = s + "!" }
}
''')
        self.assertEqual(result['s'], '{ true // # }!')

    def test_comment_braces_and_formatted_strings(self):
        result = run('name = "Taylan"\n// ignored { bracket\ntext = f"Hi {name}!"\n')
        self.assertEqual(result['text'], 'Hi Taylan!')
        self.assertEqual(run('x = 1 // comment }\ny = 2')['y'], 2)

    def test_timing(self):
        with patch('interpreter.every', return_value=iter([0.0, 0.1])):
            result = run('count = 0\nevery 100 ms for 2 s { count += 1 }')
        self.assertEqual(result['count'], 2)
        with self.assertRaises(LanguageError):
            translate('every 0 ms for 1 s {}')

    def test_errors(self):
        for source in ['x =', 'if true {', '}', 'x = [1, 2)']:
            with self.subTest(source=source), self.assertRaises(LanguageError):
                run(source)
        with self.assertRaisesRegex(LanguageError, 'Line 4:'):
            run('\n\nif true {\n    x = missing\n}')
        with self.assertRaisesRegex(LanguageError, 'Execution limit'):
            run('while true {}', max_steps=20)

    def test_class_timed_method(self):
        with patch('interpreter.every', return_value=iter([0.0, 0.1])):
            result = run('class Counter {\n def count(self) {\n value = 0\n every 100 ms for 2 s { value += 1 }\n return value\n }\n}\nresult = Counter().count()')
        self.assertEqual(result['result'], 2)

    def test_java_boolean_and_else_if(self):
        result = run('x = 2\nif (x == 1 && false)\n{\n label = "one"\n}\nelse if (x == 2 || missing)\n{\n label = "two"\n}\nelse\n{\n label = "other"\n}')
        self.assertEqual(result['label'], 'two')

    def test_cleanup(self):
        result = run('''
from mylang.robot import Robot
robot = Robot()
try {
    with robot { raise ValueError("test") }
} except ValueError { closed = robot.closed }
''')
        self.assertTrue(result['closed'])
