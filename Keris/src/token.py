"""Token definitions for the Keris lexer."""

from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    IDENTIFIER = auto()
    
    # Keywords
    IF = auto()
    ELSE = auto()
    ELIF = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    BREAK = auto()
    CONTINUE = auto()
    RETURN = auto()
    DEF = auto()
    LET = auto()
    CONST = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IMPORT = auto()
    FROM = auto()
    TRY = auto()
    CATCH = auto()
    THROW = auto()
    
    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    STAR_STAR = auto()  # **
    EQUAL = auto()
    EQUAL_EQUAL = auto()  # ==
    BANG = auto()
    BANG_EQUAL = auto()  # !=
    LESS = auto()
    LESS_EQUAL = auto()  # <=
    GREATER = auto()
    GREATER_EQUAL = auto()  # >=
    
    # Punctuation
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COMMA = auto()
    DOT = auto()
    SEMICOLON = auto()
    COLON = auto()
    
    # Special
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    """Represents a token in the source code."""
    type: TokenType
    lexeme: str
    literal: object
    line: int
    column: int
    
    def __repr__(self):
        return f"Token({self.type.name}, {self.lexeme!r}, {self.literal!r})"


# Keyword mapping
KEYWORDS = {
    "if": TokenType.IF,
    "else": TokenType.ELSE,
    "elif": TokenType.ELIF,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "return": TokenType.RETURN,
    "def": TokenType.DEF,
    "let": TokenType.LET,
    "const": TokenType.CONST,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "nil": TokenType.NIL,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "import": TokenType.IMPORT,
    "from": TokenType.FROM,
    "try": TokenType.TRY,
    "catch": TokenType.CATCH,
    "throw": TokenType.THROW,
}
