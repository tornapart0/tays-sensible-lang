import argparse
import operator
import re
from pathlib import Path

class LanguageError(Exception):
    pass

TOKEN = re.compile(
    r'(?P<SPACE>[ \t\r]+)|(?P<COMMENT>\#[^\n]*|//[^\n]*)'
    r'|(?P<NEWLINE>\n)|(?P<NUMBER>\d+(?:\.\d+)?)'
    r'|(?P<STRING>"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')'
    r'|(?P<NAME>[A-Za-z_][A-Za-z_0-9]*)'
    r'|(?P<SYMBOL>==|!=|<=|>=|[+*/%<>=!(){},;\-])'
)

def tokenize(source):
    tokens = []
    position, line = 0, 1
    while position < len(source):
        match = TOKEN.match(source, position)
        if not match:
            raise LanguageError(f'Line {line}: unexpected character {source[position]!r}')
        kind, value = match.lastgroup, match.group()
        if kind not in ('SPACE', 'COMMENT'):
            tokens.append((kind, value, line))
        line += value.count('\n')
        position = match.end()
    tokens.append(('EOF', '<end>', line))
    return tokens

class Parser:
    PRECEDENCE = {'or': 1, 'and': 2, '==': 3, '!=': 3, '<': 4, '>': 4,
                  '<=': 4, '>=': 4, '+': 5, '-': 5, '*': 6, '/': 6, '%': 6}

    def __init__(self, source):
        self.tokens = tokenize(source)
        self.position = 0

    @property
    def current(self):
        return self.tokens[self.position]

    def take(self):
        token = self.current
        if token[0] == 'EOF':
            self.fail('unexpected end of file')
        self.position += 1
        return token

    def accept(self, value):
        if self.current[1] == value:
            self.take()
            return True
        return False

    def expect(self, value):
        if not self.accept(value):
            self.fail(f'expected {value!r}, found {self.current[1]!r}')

    def fail(self, message):
        raise LanguageError(f'Line {self.current[2]}: {message}')

    def separators(self):
        while self.current[0] == 'NEWLINE' or self.current[1] == ';':
            self.take()

    def program(self, inside_block=False):
        statements = []
        self.separators()
        while self.current[0] != 'EOF' and self.current[1] != '}':
            statements.append(self.statement())
            if self.current[0] not in ('NEWLINE', 'EOF') and self.current[1] not in (';', '}'):
                self.fail('expected a newline or semicolon between statements')
            self.separators()
        if inside_block:
            self.expect('}')
        elif self.current[1] == '}':
            self.fail('unexpected closing brace')
        return statements

    def block(self):
        self.separators()
        self.expect('{')
        return self.program(inside_block=True)

    def statement(self):
        line = self.current[2]
        if self.accept('if'):
            condition = self.expression()
            yes = self.block()

            saved = self.position
            self.separators()
            if self.accept('else'):
                no = self.block()
            else:
                self.position = saved
                no = []
            return ('if', line, condition, yes, no)
        if self.accept('while'):
            condition = self.expression()
            return ('while', line, condition, self.block())
        if self.current[0] == 'NAME' and self.tokens[self.position + 1][1] == '=':
            name = self.take()[1]
            if name in ('true', 'false', 'and', 'or', 'not', 'print'):
                self.fail(f'{name!r} is reserved')
            self.expect('=')
            return ('assign', line, name, self.expression())
        if self.accept('print'):
            self.expect('(')
            arguments = []
            if not self.accept(')'):
                arguments.append(self.expression())
                while self.accept(','):
                    arguments.append(self.expression())
                self.expect(')')
            return ('print', line, arguments)
        self.fail('expected assignment, print, if, or while')

    def expression(self, minimum=1):
        kind, value, _ = self.take()
        if kind == 'NUMBER':
            left = ('literal', float(value) if '.' in value else int(value))
        elif kind == 'STRING':

            import ast
            try:
                left = ('literal', ast.literal_eval(value))
            except (SyntaxError, ValueError):
                self.fail('invalid string literal')
        elif value in ('true', 'false'):
            left = ('literal', value == 'true')
        elif value in ('-', '+', '!', 'not'):
            left = ('unary', value, self.expression(7))
        elif value == '(':
            left = self.expression()
            self.expect(')')
        elif kind == 'NAME':
            left = ('variable', value)
        else:
            self.fail(f'expected an expression, found {value!r}')
        while self.PRECEDENCE.get(self.current[1], 0) >= minimum:
            operation = self.take()[1]
            right = self.expression(self.PRECEDENCE[operation] + 1)
            left = ('binary', operation, left, right)
        return left

OPERATIONS = {'+': operator.add, '-': operator.sub, '*': operator.mul,
              '/': operator.truediv, '%': operator.mod, '==': operator.eq,
              '!=': operator.ne, '<': operator.lt, '>': operator.gt,
              '<=': operator.le, '>=': operator.ge}

class Interpreter:
    def __init__(self, max_steps=100_000):
        self.variables = {}
        self.steps = 0
        self.max_steps = max_steps

    def evaluate(self, node):
        kind = node[0]
        if kind == 'literal':
            return node[1]
        if kind == 'variable':
            if node[1] not in self.variables:
                raise LanguageError(f'unknown variable {node[1]!r}')
            return self.variables[node[1]]
        if kind == 'unary':
            value = self.evaluate(node[2])
            if node[1] in ('!', 'not'):
                return not value
            return -value if node[1] == '-' else +value
        operation = node[1]
        left = self.evaluate(node[2])
        if operation == 'and':
            return bool(left) and bool(self.evaluate(node[3]))
        if operation == 'or':
            return bool(left) or bool(self.evaluate(node[3]))
        return OPERATIONS[operation](left, self.evaluate(node[3]))

    def tick(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise LanguageError('execution limit reached; check for an endless loop')

    def execute(self, statements):
        for statement in statements:
            kind, line, *parts = statement
            try:
                self.tick()
                if kind == 'assign':
                    self.variables[parts[0]] = self.evaluate(parts[1])
                elif kind == 'print':
                    print(*(self.evaluate(item) for item in parts[0]))
                elif kind == 'if':
                    self.execute(parts[1] if self.evaluate(parts[0]) else parts[2])
                elif kind == 'while':
                    while self.evaluate(parts[0]):
                        self.tick()
                        self.execute(parts[1])
            except LanguageError as error:
                if str(error).startswith('Line '):
                    raise
                raise LanguageError(f'Line {line}: {error}') from None
            except (TypeError, ValueError, ZeroDivisionError, OverflowError) as error:
                raise LanguageError(f'Line {line}: {error}') from None

def run(source, max_steps=100_000):
    interpreter = Interpreter(max_steps)
    interpreter.execute(Parser(source).program())
    return interpreter.variables

def main():
    arguments = argparse.ArgumentParser(description='Run a MyLang source file.')
    arguments.add_argument('file', type=Path)
    arguments.add_argument('--max-steps', type=int, default=100_000)
    options = arguments.parse_args()
    try:
        run(options.file.read_text(encoding='utf-8'), options.max_steps)
    except (OSError, LanguageError, RecursionError) as error:
        arguments.exit(1, f'{error}\n')

if __name__ == '__main__':
    main()
