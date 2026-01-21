"""Lexer (tokenizer) for the Keris programming language."""

from .token import Token, TokenType, KEYWORDS


class Lexer:
    """Tokenizes Keris source code."""
    
    def __init__(self, source: str):
        self.source = source
        self.tokens = []
        self.start = 0
        self.current = 0
        self.line = 1
        self.column = 1
        self.start_column = 1
    
    def scan_tokens(self) -> list[Token]:
        """Scan the source code and return a list of tokens."""
        while not self.is_at_end():
            self.start = self.current
            self.start_column = self.column
            self.scan_token()
        
        self.tokens.append(Token(
            TokenType.EOF, "", None, self.line, self.column
        ))
        return self.tokens
    
    def scan_token(self):
        """Scan a single token."""
        char = self.advance()
        
        if char == '(':
            self.add_token(TokenType.LEFT_PAREN)
        elif char == ')':
            self.add_token(TokenType.RIGHT_PAREN)
        elif char == '{':
            self.add_token(TokenType.LEFT_BRACE)
        elif char == '}':
            self.add_token(TokenType.RIGHT_BRACE)
        elif char == '[':
            self.add_token(TokenType.LEFT_BRACKET)
        elif char == ']':
            self.add_token(TokenType.RIGHT_BRACKET)
        elif char == ',':
            self.add_token(TokenType.COMMA)
        elif char == '.':
            self.add_token(TokenType.DOT)
        elif char == ';':
            self.add_token(TokenType.SEMICOLON)
        elif char == ':':
            self.add_token(TokenType.COLON)
        elif char == '+':
            self.add_token(TokenType.PLUS)
        elif char == '-':
            self.add_token(TokenType.MINUS)
        elif char == '*':
            if self.match('*'):
                self.add_token(TokenType.STAR_STAR)
            else:
                self.add_token(TokenType.STAR)
        elif char == '/':
            if self.match('/'):
                # Single-line comment (//)
                while self.peek() != '\n' and not self.is_at_end():
                    self.advance()
            elif self.match('*'):
                # Multi-line comment
                self.scan_multiline_comment()
            else:
                self.add_token(TokenType.SLASH)
        elif char == '#':
            # Single-line comment (#)
            while self.peek() != '\n' and not self.is_at_end():
                self.advance()
        elif char == '%':
            self.add_token(TokenType.PERCENT)
        elif char == '!':
            self.add_token(TokenType.BANG_EQUAL if self.match('=') else TokenType.BANG)
        elif char == '=':
            self.add_token(TokenType.EQUAL_EQUAL if self.match('=') else TokenType.EQUAL)
        elif char == '<':
            self.add_token(TokenType.LESS_EQUAL if self.match('=') else TokenType.LESS)
        elif char == '>':
            self.add_token(TokenType.GREATER_EQUAL if self.match('=') else TokenType.GREATER)
        elif char == ' ' or char == '\r' or char == '\t':
            # Ignore whitespace
            pass
        elif char == '\n':
            self.line += 1
            self.column = 1
            self.add_token(TokenType.NEWLINE)
        elif char == '"' or char == "'":
            self.scan_string(char)
        elif char.isdigit():
            self.scan_number()
        elif char.isalpha() or char == '_':
            self.scan_identifier()
        else:
            raise SyntaxError(
                f"Unexpected character '{char}' at line {self.line}, column {self.column}"
            )
    
    def scan_multiline_comment(self):
        """Scan a multi-line comment /* ... */."""
        while not self.is_at_end():
            if self.peek() == '*' and self.peek_next() == '/':
                self.advance()  # consume '*'
                self.advance()  # consume '/'
                return
            if self.peek() == '\n':
                self.line += 1
                self.column = 1
            self.advance()
        raise SyntaxError("Unterminated multi-line comment")
    
    def scan_string(self, quote_char: str):
        """Scan a string literal."""
        while self.peek() != quote_char and not self.is_at_end():
            if self.peek() == '\n':
                self.line += 1
                self.column = 1
            elif self.peek() == '\\':
                self.advance()  # consume backslash
                # Handle escape sequences
                if self.peek() == 'n':
                    self.advance()
                elif self.peek() == 't':
                    self.advance()
                elif self.peek() == '\\':
                    self.advance()
                elif self.peek() == quote_char:
                    self.advance()
                elif self.peek() == '"':
                    self.advance()
            self.advance()
        
        if self.is_at_end():
            raise SyntaxError("Unterminated string")
        
        # Consume closing quote
        self.advance()
        
        # Extract string value and process escape sequences
        value = self.source[self.start + 1:self.current - 1]
        value = value.replace('\\n', '\n')
        value = value.replace('\\t', '\t')
        value = value.replace('\\\\', '\\')
        value = value.replace('\\' + quote_char, quote_char)
        
        self.add_token(TokenType.STRING, value)
    
    def scan_number(self):
        """Scan a number literal."""
        while self.peek().isdigit():
            self.advance()
        
        # Look for decimal point
        if self.peek() == '.' and self.peek_next().isdigit():
            self.advance()  # consume '.'
            while self.peek().isdigit():
                self.advance()
        
        # Look for scientific notation
        if self.peek().lower() == 'e':
            self.advance()  # consume 'e'
            if self.peek() == '+' or self.peek() == '-':
                self.advance()
            while self.peek().isdigit():
                self.advance()
        
        value = float(self.source[self.start:self.current])
        # Use int if it's a whole number
        if value.is_integer():
            value = int(value)
        self.add_token(TokenType.NUMBER, value)
    
    def scan_identifier(self):
        """Scan an identifier or keyword."""
        while self.peek().isalnum() or self.peek() == '_':
            self.advance()
        
        text = self.source[self.start:self.current]
        token_type = KEYWORDS.get(text, TokenType.IDENTIFIER)
        
        # Handle boolean and nil literals
        if token_type == TokenType.TRUE:
            self.add_token(token_type, True)
        elif token_type == TokenType.FALSE:
            self.add_token(token_type, False)
        elif token_type == TokenType.NIL:
            self.add_token(token_type, None)
        else:
            self.add_token(token_type)
    
    def match(self, expected: str) -> bool:
        """Check if current character matches expected and consume it if so."""
        if self.is_at_end():
            return False
        if self.source[self.current] != expected:
            return False
        self.current += 1
        self.column += 1
        return True
    
    def peek(self) -> str:
        """Look at current character without consuming it."""
        if self.is_at_end():
            return '\0'
        return self.source[self.current]
    
    def peek_next(self) -> str:
        """Look at next character without consuming it."""
        if self.current + 1 >= len(self.source):
            return '\0'
        return self.source[self.current + 1]
    
    def advance(self) -> str:
        """Consume and return current character."""
        if self.is_at_end():
            return '\0'
        char = self.source[self.current]
        self.current += 1
        self.column += 1
        return char
    
    def is_at_end(self) -> bool:
        """Check if we've consumed all source code."""
        return self.current >= len(self.source)
    
    def add_token(self, token_type: TokenType, literal=None):
        """Add a token to the tokens list."""
        text = self.source[self.start:self.current]
        if literal is None:
            literal = text
        self.tokens.append(Token(
            token_type, text, literal, self.line, self.start_column
        ))
