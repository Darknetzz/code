"""Parser for the Keris programming language."""

from typing import Optional, List
from .token import Token, TokenType
from .ast import *


class ParseError(Exception):
    """Raised when a parse error occurs."""
    pass


class Parser:
    """Parses tokens into an Abstract Syntax Tree."""
    
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.current = 0
    
    def parse(self) -> List[Stmt]:
        """Parse tokens into a list of statements."""
        statements = []
        while not self.is_at_end():
            if self.check(TokenType.NEWLINE):
                self.advance()  # Skip newlines
                continue
            statements.append(self.declaration())
        return statements
    
    def declaration(self) -> Stmt:
        """Parse a declaration (variable or function)."""
        try:
            if self.match(TokenType.LET):
                return self.var_declaration(False)
            if self.match(TokenType.CONST):
                return self.var_declaration(True)
            if self.match(TokenType.DEF):
                return self.function_declaration()
            return self.statement()
        except ParseError as e:
            self.synchronize()
            raise
    
    def var_declaration(self, is_const: bool) -> Stmt:
        """Parse a variable declaration."""
        name = self.consume(TokenType.IDENTIFIER, "Expected variable name").lexeme
        self.consume(TokenType.EQUAL, "Expected '=' after variable name")
        initializer = self.expression()
        return Var(name, initializer, is_const)
    
    def function_declaration(self) -> Stmt:
        """Parse a function declaration."""
        name = self.consume(TokenType.IDENTIFIER, "Expected function name").lexeme
        self.consume(TokenType.LEFT_PAREN, "Expected '(' after function name")
        
        params = []
        if not self.check(TokenType.RIGHT_PAREN):
            params.append(self.consume(TokenType.IDENTIFIER, "Expected parameter name").lexeme)
            while self.match(TokenType.COMMA):
                params.append(self.consume(TokenType.IDENTIFIER, "Expected parameter name").lexeme)
        
        self.consume(TokenType.RIGHT_PAREN, "Expected ')' after parameters")
        self.consume(TokenType.LEFT_BRACE, "Expected '{' before function body")
        body = self.block_statements()
        return Function(name, params, body)
    
    def statement(self) -> Stmt:
        """Parse a statement."""
        if self.match(TokenType.IF):
            return self.if_statement()
        if self.match(TokenType.WHILE):
            return self.while_statement()
        if self.match(TokenType.FOR):
            return self.for_statement()
        if self.match(TokenType.BREAK):
            return Break()
        if self.match(TokenType.CONTINUE):
            return Continue()
        if self.match(TokenType.RETURN):
            return self.return_statement()
        if self.match(TokenType.TRY):
            return self.try_statement()
        if self.match(TokenType.LEFT_BRACE):
            return Block(self.block_statements())
        return self.expression_statement()
    
    def if_statement(self) -> Stmt:
        """Parse an if statement."""
        condition = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after if condition")
        then_branch = Block(self.block_statements())
        
        else_branch = None
        if self.match(TokenType.ELIF):
            else_branch = self.if_statement()  # Recursive for elif
        elif self.match(TokenType.ELSE):
            self.consume(TokenType.LEFT_BRACE, "Expected '{' after else")
            else_branch = Block(self.block_statements())
        
        return If(condition, then_branch, else_branch)
    
    def while_statement(self) -> Stmt:
        """Parse a while statement."""
        condition = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after while condition")
        body = Block(self.block_statements())
        return While(condition, body)
    
    def for_statement(self) -> Stmt:
        """Parse a for statement."""
        var_name = self.consume(TokenType.IDENTIFIER, "Expected variable name after 'for'").lexeme
        self.consume(TokenType.IN, "Expected 'in' after for variable")
        iterable = self.expression()
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after for iterable")
        body = Block(self.block_statements())
        return For(var_name, iterable, body)
    
    def return_statement(self) -> Stmt:
        """Parse a return statement."""
        value = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.SEMICOLON) and not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            value = self.expression()
        return Return(value)
    
    def try_statement(self) -> Stmt:
        """Parse a try-catch statement."""
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after try")
        try_block = Block(self.block_statements())
        self.consume(TokenType.CATCH, "Expected 'catch' after try block")
        catch_var = self.consume(TokenType.IDENTIFIER, "Expected variable name after 'catch'").lexeme
        self.consume(TokenType.LEFT_BRACE, "Expected '{' after catch variable")
        catch_block = Block(self.block_statements())
        return Try(try_block, catch_var, catch_block)
    
    def block_statements(self) -> List[Stmt]:
        """Parse statements until closing brace."""
        statements = []
        while not self.check(TokenType.RIGHT_BRACE) and not self.is_at_end():
            if self.check(TokenType.NEWLINE):
                self.advance()  # Skip newlines
                continue
            statements.append(self.declaration())
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after block")
        return statements
    
    def expression_statement(self) -> Stmt:
        """Parse an expression statement."""
        expr = self.expression()
        # Optional semicolon or newline
        self.match(TokenType.SEMICOLON)
        self.match(TokenType.NEWLINE)
        return Expression(expr)
    
    def expression(self) -> Expr:
        """Parse an expression."""
        return self.assignment()
    
    def assignment(self) -> Expr:
        """Parse an assignment expression."""
        expr = self.logic_or()
        
        if self.match(TokenType.EQUAL):
            equals = self.previous()
            value = self.assignment()
            
            if isinstance(expr, Identifier):
                return Assign(expr.name, value)
            elif isinstance(expr, Get):
                return Set(expr.obj, expr.name, value)
            elif isinstance(expr, Index):
                return IndexSet(expr.obj, expr.index, value)
            
            raise ParseError(f"Invalid assignment target at line {equals.line}")
        
        return expr
    
    def logic_or(self) -> Expr:
        """Parse logical OR expression."""
        expr = self.logic_and()
        while self.match(TokenType.OR):
            operator = self.previous()
            right = self.logic_and()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def logic_and(self) -> Expr:
        """Parse logical AND expression."""
        expr = self.equality()
        while self.match(TokenType.AND):
            operator = self.previous()
            right = self.equality()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def equality(self) -> Expr:
        """Parse equality expression."""
        expr = self.comparison()
        while self.match(TokenType.EQUAL_EQUAL, TokenType.BANG_EQUAL):
            operator = self.previous()
            right = self.comparison()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def comparison(self) -> Expr:
        """Parse comparison expression."""
        expr = self.term()
        while self.match(TokenType.GREATER, TokenType.GREATER_EQUAL, TokenType.LESS, TokenType.LESS_EQUAL):
            operator = self.previous()
            right = self.term()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def term(self) -> Expr:
        """Parse addition/subtraction expression."""
        expr = self.factor()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            operator = self.previous()
            right = self.factor()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def factor(self) -> Expr:
        """Parse multiplication/division expression."""
        expr = self.unary()
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            operator = self.previous()
            right = self.unary()
            expr = Binary(expr, operator.lexeme, right)
        return expr
    
    def unary(self) -> Expr:
        """Parse unary expression."""
        if self.match(TokenType.BANG, TokenType.MINUS, TokenType.NOT):
            operator = self.previous()
            right = self.unary()
            return Unary(operator.lexeme, right)
        return self.exponentiation()
    
    def exponentiation(self) -> Expr:
        """Parse exponentiation expression."""
        expr = self.call()
        if self.match(TokenType.STAR_STAR):
            operator = self.previous()
            right = self.exponentiation()
            return Binary(expr, operator.lexeme, right)
        return expr
    
    def call(self) -> Expr:
        """Parse function call, member access, and indexing."""
        expr = self.primary()
        
        while True:
            if self.match(TokenType.LEFT_PAREN):
                expr = self.finish_call(expr)
            elif self.match(TokenType.LEFT_BRACKET):
                index = self.expression()
                self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after index")
                expr = Index(expr, index)
            elif self.match(TokenType.DOT):
                name = self.consume(TokenType.IDENTIFIER, "Expected property name after '.'").lexeme
                expr = Get(expr, name)
            else:
                break
        
        return expr
    
    def finish_call(self, callee: Expr) -> Expr:
        """Finish parsing a function call."""
        arguments = []
        if not self.check(TokenType.RIGHT_PAREN):
            arguments.append(self.expression())
            while self.match(TokenType.COMMA):
                arguments.append(self.expression())
        
        paren = self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments")
        return Call(callee, arguments)
    
    def primary(self) -> Expr:
        """Parse a primary expression."""
        if self.match(TokenType.FALSE):
            return Literal(False)
        if self.match(TokenType.TRUE):
            return Literal(True)
        if self.match(TokenType.NIL):
            return Literal(None)
        if self.match(TokenType.NUMBER, TokenType.STRING):
            return Literal(self.previous().literal)
        if self.match(TokenType.LEFT_PAREN):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression")
            return expr
        if self.match(TokenType.LEFT_BRACKET):
            return self.list_literal()
        if self.match(TokenType.LEFT_BRACE):
            return self.dict_literal()
        if self.match(TokenType.IDENTIFIER):
            return Identifier(self.previous().lexeme)
        if self.match(TokenType.THROW):
            value = self.expression()
            return Throw(value)  # Treat throw as expression for now
        
        raise ParseError(f"Expected expression at line {self.peek().line}")
    
    def list_literal(self) -> Expr:
        """Parse a list literal."""
        elements = []
        if not self.check(TokenType.RIGHT_BRACKET):
            elements.append(self.expression())
            while self.match(TokenType.COMMA):
                elements.append(self.expression())
        self.consume(TokenType.RIGHT_BRACKET, "Expected ']' after list elements")
        return ListLiteral(elements)
    
    def dict_literal(self) -> Expr:
        """Parse a dictionary literal."""
        pairs = []
        if not self.check(TokenType.RIGHT_BRACE):
            key = self.expression()
            self.consume(TokenType.COLON, "Expected ':' after dictionary key")
            value = self.expression()
            pairs.append((key, value))
            while self.match(TokenType.COMMA):
                key = self.expression()
                self.consume(TokenType.COLON, "Expected ':' after dictionary key")
                value = self.expression()
                pairs.append((key, value))
        self.consume(TokenType.RIGHT_BRACE, "Expected '}' after dictionary pairs")
        return DictLiteral(pairs)
    
    def match(self, *types: TokenType) -> bool:
        """Check if current token matches any of the given types."""
        for token_type in types:
            if self.check(token_type):
                self.advance()
                return True
        return False
    
    def check(self, token_type: TokenType) -> bool:
        """Check if current token is of given type."""
        if self.is_at_end():
            return False
        return self.peek().type == token_type
    
    def advance(self) -> Token:
        """Advance to next token."""
        if not self.is_at_end():
            self.current += 1
        return self.previous()
    
    def is_at_end(self) -> bool:
        """Check if we've consumed all tokens."""
        return self.peek().type == TokenType.EOF
    
    def peek(self) -> Token:
        """Get current token without consuming it."""
        return self.tokens[self.current]
    
    def previous(self) -> Token:
        """Get previous token."""
        return self.tokens[self.current - 1]
    
    def consume(self, token_type: TokenType, message: str) -> Token:
        """Consume token of expected type or raise error."""
        if self.check(token_type):
            return self.advance()
        raise ParseError(f"{message} at line {self.peek().line}, column {self.peek().column}")
    
    def synchronize(self):
        """Synchronize parser after error."""
        self.advance()
        while not self.is_at_end():
            if self.previous().type == TokenType.SEMICOLON or self.previous().type == TokenType.NEWLINE:
                return
            
            if self.peek().type in (
                TokenType.DEF, TokenType.LET, TokenType.CONST,
                TokenType.FOR, TokenType.IF, TokenType.WHILE, TokenType.RETURN
            ):
                return
            
            self.advance()
