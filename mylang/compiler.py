import io
import re
import tokenize
from dataclasses import dataclass

class LanguageError(Exception):
    pass

@dataclass
class Translation:
    code: str
    lines: dict

HEADERS = {'if', 'elif', 'else', 'while', 'for', 'def', 'class', 'with',
           'try', 'except', 'finally', 'async', 'match', 'case', 'repeat', 'every'}
ALIASES = {'true': 'True', 'false': 'False', 'null': 'None'}

def normalize_comments(source):

    comments = {}
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.OP and token.string == '//':
                comments.setdefault(token.start[0], token.start[1])
    except (tokenize.TokenError, IndentationError):

        pass
    lines = source.splitlines(keepends=True)
    for line, column in comments.items():
        original = lines[line - 1]
        ending = '\n' if original.endswith('\n') else ''
        lines[line - 1] = original[:column] + '#' + ending
    return ''.join(lines)

def translate(source):
    source = normalize_comments(source)
    source_lines = source.splitlines(keepends=True)
    offsets = [0]
    for source_line in source_lines:
        offsets.append(offsets[-1] + len(source_line))
    output, lines, statement, delimiters, blocks = [], {}, [], [], []
    start = 1
    awaiting_block = False

    def emit(text, line):
        for index, part in enumerate(text.split('\n')):
            output.append(('    ' * len(blocks) if index == 0 else '') + part)
            lines[len(output)] = line + index
        if blocks:
            blocks[-1] = True

    def flush():
        nonlocal statement
        if statement:
            emit(' '.join(statement), start)
            statement = []

    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            kind, value, (line, _), _, _ = token
            if kind in (tokenize.ENCODING, tokenize.INDENT, tokenize.DEDENT,
                        tokenize.ENDMARKER):
                continue
            if kind == tokenize.COMMENT:
                continue
            if kind == tokenize.ERRORTOKEN and value.isspace():
                continue
            if kind in (tokenize.NEWLINE, tokenize.NL):
                if not delimiters and not awaiting_block:
                    flush()
                continue
            if not statement:
                start = line
            if kind == getattr(tokenize, 'FSTRING_START', -1):
                depth = 1
                end_position = token.end
                for piece in tokens:
                    if piece.type == tokenize.FSTRING_START:
                        depth += 1
                    elif piece.type == tokenize.FSTRING_END:
                        depth -= 1
                    end_position = piece.end
                    if depth == 0:
                        break
                if depth:
                    raise LanguageError(f'Line {line}: unclosed formatted string')
                begin = offsets[token.start[0] - 1] + token.start[1]
                finish = offsets[end_position[0] - 1] + end_position[1]
                statement.append(source[begin:finish])
                continue
            header = bool(statement and statement[0] in HEADERS)
            if value == '{' and not delimiters and header:
                text = ' '.join(statement).rstrip()
                if text.endswith(':'):
                    text = text[:-1]
                if text.startswith('else if '):
                    text = 'elif ' + text[8:]
                if statement[0] == 'repeat':
                    text = f'for _mylang_repeat_{len(output)} in range({text[7:]}):'
                elif statement[0] == 'every':
                    pattern = r'every\s+([0-9]+(?:\s*\.\s*[0-9]+)?)\s+(ms|s)\s+for\s+([0-9]+(?:\s*\.\s*[0-9]+)?)\s+(ms|s)'
                    match = re.fullmatch(pattern, text)
                    if not match:
                        raise LanguageError(f'Line {start}: use every 100 ms for 2 s {{ ... }}')
                    interval, unit, duration, end_unit = match.groups()
                    interval = float(interval.replace(' ', '')) / (1000 if unit == 'ms' else 1)
                    duration = float(duration.replace(' ', '')) / (1000 if end_unit == 'ms' else 1)
                    if interval <= 0:
                        raise LanguageError(f'Line {start}: sampling interval must be positive')
                    text = f'for _mylang_tick_{len(output)} in _mylang_every({interval}, {duration}):'
                else:
                    text += ':'
                emit(text, start)
                statement = []
                blocks.append(False)
                awaiting_block = False
                continue
            if value == '}' and not delimiters:
                flush()
                if not blocks:
                    raise LanguageError(f'Line {line}: unexpected closing brace')
                if not blocks[-1]:
                    emit('pass', line)
                blocks.pop()
                awaiting_block = False
                continue
            if value == ';' and not delimiters:
                flush()
                continue
            if value in ('(', '[', '{'):
                delimiters.append(value)
            elif value in (')', ']', '}'):
                expected = {')': '(', ']': '[', '}': '{'}[value]
                if not delimiters or delimiters.pop() != expected:
                    raise LanguageError(f'Line {line}: mismatched {value!r}')
            if value in ('&', '|') and statement and statement[-1] == value:
                statement.pop()
                value = 'and' if value == '&' else 'or'
            if kind == tokenize.NAME:
                value = ALIASES.get(value, value)
            elif value == '!':
                value = 'not'
            statement.append(value)
            awaiting_block = bool(statement[0] in HEADERS and not delimiters)
        flush()
        if blocks or delimiters:
            raise LanguageError('Unclosed block or expression')
    except (tokenize.TokenError, IndentationError) as error:
        raise LanguageError(f'Invalid source: {error}') from None
    code = '\n'.join(output) + '\n'
    try:
        compile(code, '<mylang>', 'exec')
    except SyntaxError as error:
        line = lines.get(error.lineno, error.lineno)
        raise LanguageError(f'Line {line}: {error.msg}') from None
    return Translation(code, lines)
