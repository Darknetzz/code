"""Basic tests for the Keris interpreter."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.lexer import Lexer
from src.parser import Parser
from src.interpreter import Interpreter
from src.runtime import RuntimeError


def run_test(source: str, expected_output: str = None):
    """Run a test and optionally check output."""
    lexer = Lexer(source)
    tokens = lexer.scan_tokens()
    
    parser = Parser(tokens)
    statements = parser.parse()
    
    interpreter = Interpreter()
    
    # Capture output
    import io
    from contextlib import redirect_stdout
    
    f = io.StringIO()
    with redirect_stdout(f):
        try:
            interpreter.interpret(statements)
        except RuntimeError as e:
            print(f"Runtime error: {e}")
    
    output = f.getvalue()
    
    if expected_output:
        assert output.strip() == expected_output.strip(), f"Expected '{expected_output}', got '{output}'"
    
    return output


def test_hello_world():
    """Test hello world."""
    run_test('print("Hello, World!")', "Hello, World!\n")
    print("[OK] Hello world test passed")


def test_variables():
    """Test variable declarations."""
    run_test("""
    let x = 10
    print(x)
    """, "10\n")
    print("[OK] Variables test passed")


def test_functions():
    """Test function definitions and calls."""
    run_test("""
    def add(a, b) {
        return a + b
    }
    print(add(5, 3))
    """, "8\n")
    print("[OK] Functions test passed")


def test_arithmetic():
    """Test arithmetic operations."""
    run_test("""
    print(2 + 3)
    print(10 - 4)
    print(3 * 4)
    print(15 / 3)
    print(2 ** 3)
    """, "5\n6\n12\n5.0\n8\n")
    print("[OK] Arithmetic test passed")


def test_control_flow():
    """Test control flow."""
    run_test("""
    let x = 5
    if x > 3 {
        print("x is greater than 3")
    } else {
        print("x is not greater than 3")
    }
    """, "x is greater than 3\n")
    print("[OK] Control flow test passed")


def test_lists():
    """Test list operations."""
    run_test("""
    let lst = [1, 2, 3]
    print(list.len(lst))
    print(list.contains(lst, 2))
    """, "3\nTrue\n")  # Python prints True with capital T
    print("[OK] Lists test passed")


def test_all():
    """Run all tests."""
    print("Running Keris tests...\n")
    try:
        test_hello_world()
        test_variables()
        test_functions()
        test_arithmetic()
        test_control_flow()
        test_lists()
        print("\n[SUCCESS] All tests passed!")
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    test_all()
