"""Main entry point for the Keris interpreter."""

import sys
from .lexer import Lexer
from .parser import Parser, ParseError
from .interpreter import Interpreter
from .runtime import RuntimeError


def run(source: str) -> None:
    """Run Keris source code."""
    lexer = Lexer(source)
    tokens = lexer.scan_tokens()
    
    parser = Parser(tokens)
    try:
        statements = parser.parse()
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        sys.exit(1)
    
    interpreter = Interpreter()
    try:
        interpreter.interpret(statements)
    except RuntimeError as e:
        print(f"Runtime error: {e}", file=sys.stderr)
        sys.exit(1)


def run_file(filename: str) -> None:
    """Run a Keris source file."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()
        run(source)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found", file=sys.stderr)
        sys.exit(1)
    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)


def run_prompt() -> None:
    """Run the Keris REPL."""
    interpreter = Interpreter()
    print("Keris v1.0.0")
    print("Type 'exit' or 'quit' to exit")
    print()
    
    while True:
        try:
            line = input("keris> ")
            if line.strip() in ("exit", "quit"):
                break
            if not line.strip():
                continue
            
            # Try to parse and execute
            lexer = Lexer(line)
            tokens = lexer.scan_tokens()
            
            parser = Parser(tokens)
            try:
                statements = parser.parse()
                interpreter.interpret(statements)
            except ParseError as e:
                print(f"Parse error: {e}", file=sys.stderr)
            except RuntimeError as e:
                print(f"Runtime error: {e}", file=sys.stderr)
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            break


def main():
    """Main entry point."""
    if len(sys.argv) > 2:
        print("Usage: keris [script]", file=sys.stderr)
        sys.exit(1)
    elif len(sys.argv) == 2:
        run_file(sys.argv[1])
    else:
        run_prompt()


if __name__ == "__main__":
    main()
