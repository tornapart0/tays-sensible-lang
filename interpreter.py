import argparse
import sys
import traceback
from pathlib import Path
from mylang.compiler import LanguageError, translate
from mylang.timing import every

def run(source, max_steps=None, filename='<mylang>', arguments=None):
    translation = translate(source)
    namespace = {'__name__': '__main__', '__file__': filename, '_mylang_every': every}
    previous_trace, previous_argv = sys.gettrace(), sys.argv
    steps = 0

    def limit(frame, event, arg):
        nonlocal steps
        if frame.f_code.co_filename == filename and event == 'line':
            steps += 1
            if steps > max_steps:
                raise LanguageError('Execution limit reached; check for an endless loop')
        return limit

    try:
        sys.argv = [filename, *(arguments or [])]
        if max_steps is not None:
            sys.settrace(limit)
        exec(compile(translation.code, filename, 'exec'), namespace)
    except Exception as error:
        locations = [entry.lineno for entry in traceback.extract_tb(error.__traceback__)
                     if entry.filename == filename]
        line = translation.lines.get(locations[-1]) if locations else None
        prefix = f'Line {line}: ' if line else ''
        raise LanguageError(f'{prefix}{type(error).__name__}: {error}') from None
    finally:
        sys.argv = previous_argv
        if max_steps is not None:
            sys.settrace(previous_trace)
    return namespace

def main():
    parser = argparse.ArgumentParser(description='Run brace-style MyLang programs.')
    parser.add_argument('--check', action='store_true', help='Check syntax without running')
    parser.add_argument('--emit', type=Path, help='Save translated Python without running')
    parser.add_argument('--max-steps', type=int, help='Optional limit on MyLang line executions')
    parser.add_argument('file', type=Path)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    options = parser.parse_args()
    if options.max_steps is not None and options.max_steps < 1:
        parser.error('--max-steps must be positive')
    filename = str(options.file.resolve())
    try:
        source = options.file.read_text(encoding='utf-8')
        if options.check or options.emit:
            result = translate(source)
            if options.emit:
                options.emit.parent.mkdir(parents=True, exist_ok=True)
                options.emit.write_text('from mylang.timing import every as _mylang_every\n' + result.code, encoding='utf-8')
            print(f'Syntax OK: {options.file}')
        else:

            sys.path.insert(0, str(options.file.resolve().parent))
            run(source, options.max_steps, filename, options.arguments)
    except (OSError, LanguageError) as error:
        parser.exit(1, f'{error}\n')
    except KeyboardInterrupt:
        parser.exit(130, 'Interrupted\n')

if __name__ == '__main__':
    main()
