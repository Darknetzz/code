use anyhow::{bail, Result};
use malachite::Natural;
use malachite::num::arithmetic::traits::Pow;
use malachite::num::basic::traits::{One, Zero};
use std::str::FromStr;

use crate::progress::status_line;

const MAX_EXPONENT: u64 = 1_000_000;
const MAX_VALUE_DIGITS: u64 = 500_000;

#[derive(Debug, Clone, PartialEq, Eq)]
enum Token {
    Number(Natural),
    Plus,
    Minus,
    Star,
    Slash,
    Caret,
    LParen,
    RParen,
}

struct Lexer<'a> {
    chars: std::str::Chars<'a>,
}

impl<'a> Lexer<'a> {
    fn new(input: &'a str) -> Self {
        Self {
            chars: input.chars(),
        }
    }

    fn peek(&mut self) -> Option<char> {
        self.chars.clone().next()
    }

    fn next(&mut self) -> Option<char> {
        self.chars.next()
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek(), Some(ch) if ch.is_ascii_whitespace()) {
            self.next();
        }
    }

    fn tokenize(mut self) -> Result<Vec<Token>> {
        let mut tokens = Vec::new();

        loop {
            self.skip_whitespace();
            let Some(ch) = self.peek() else {
                break;
            };

            let token = match ch {
                '0'..='9' => {
                    let mut digits = String::new();
                    while matches!(self.peek(), Some(ch) if ch.is_ascii_digit()) {
                        digits.push(self.next().expect("digit"));
                    }
                    let number = Natural::from_str(&digits)
                        .map_err(|()| anyhow::anyhow!("invalid integer literal `{digits}`"))?;
                    Token::Number(number)
                }
                '+' => {
                    self.next();
                    Token::Plus
                }
                '-' => {
                    self.next();
                    Token::Minus
                }
                '*' => {
                    self.next();
                    Token::Star
                }
                '/' => {
                    self.next();
                    Token::Slash
                }
                '^' => {
                    self.next();
                    Token::Caret
                }
                '(' => {
                    self.next();
                    Token::LParen
                }
                ')' => {
                    self.next();
                    Token::RParen
                }
                _ => bail!("invalid character `{ch}` in expression"),
            };
            tokens.push(token);
        }

        Ok(tokens)
    }
}

struct Parser {
    tokens: Vec<Token>,
    pos: usize,
}

impl Parser {
    fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, pos: 0 }
    }

    fn has_remaining(&self) -> bool {
        self.pos < self.tokens.len()
    }

    fn peek(&self) -> Option<&Token> {
        self.tokens.get(self.pos)
    }

    fn bump(&mut self) -> Option<Token> {
        let token = self.tokens.get(self.pos).cloned();
        if token.is_some() {
            self.pos += 1;
        }
        token
    }

    fn expect(&mut self, expected: Token) -> Result<()> {
        match self.bump() {
            Some(token) if token == expected => Ok(()),
            Some(token) => bail!("expected {expected:?}, found {token:?}"),
            None => bail!("expected {expected:?}, found end of expression"),
        }
    }

    fn parse_expr(&mut self) -> Result<Natural> {
        let mut value = self.parse_term()?;

        while matches!(self.peek(), Some(Token::Plus | Token::Minus)) {
            match self.bump().expect("operator") {
                Token::Plus => value += self.parse_term()?,
                Token::Minus => {
                    let rhs = self.parse_term()?;
                    if value < rhs {
                        bail!("expression must evaluate to a positive integer");
                    }
                    value -= rhs;
                }
                _ => unreachable!(),
            }
        }

        Ok(value)
    }

    fn parse_term(&mut self) -> Result<Natural> {
        let mut value = self.parse_power()?;

        while matches!(self.peek(), Some(Token::Star | Token::Slash)) {
            match self.bump().expect("operator") {
                Token::Star => value *= self.parse_power()?,
                Token::Slash => {
                    let rhs = self.parse_power()?;
                    if rhs == Natural::ZERO {
                        bail!("division by zero");
                    }
                    value /= rhs;
                }
                _ => unreachable!(),
            }
        }

        Ok(value)
    }

    fn parse_power(&mut self) -> Result<Natural> {
        let value = self.parse_factor()?;

        if matches!(self.peek(), Some(Token::Caret)) {
            self.bump();
            let exponent = self.parse_power()?;
            return pow_natural(value, exponent);
        }

        Ok(value)
    }

    fn parse_factor(&mut self) -> Result<Natural> {
        match self.bump() {
            Some(Token::Number(value)) => Ok(value),
            Some(Token::Minus) => {
                bail!("negative values are not supported");
            }
            Some(Token::LParen) => {
                let value = self.parse_expr()?;
                self.expect(Token::RParen)?;
                Ok(value)
            }
            Some(token) => bail!("unexpected token {token:?}"),
            None => bail!("unexpected end of expression"),
        }
    }

    fn finish(self) -> Result<()> {
        if self.has_remaining() {
            bail!("unexpected trailing input");
        }
        Ok(())
    }
}

fn estimate_pow_digits(base: &Natural, exponent: u64) -> u64 {
    if exponent == 0 {
        return 1;
    }
    if base <= &Natural::ONE {
        return 1;
    }

    if let Ok(base_f) = base.to_string().parse::<f64>() {
        if base_f > 1.0 {
            return ((exponent as f64) * base_f.log10()).floor() as u64 + 1;
        }
    }

    exponent.saturating_mul(base.to_string().len() as u64)
}

fn validate_pow(base: &Natural, exponent: u64) -> Result<()> {
    if exponent > MAX_EXPONENT {
        bail!("exponent {exponent} exceeds limit of {MAX_EXPONENT}");
    }

    let estimated_digits = estimate_pow_digits(base, exponent);
    if estimated_digits > MAX_VALUE_DIGITS {
        bail!(
            "expression would produce about {estimated_digits} digits; limit is {MAX_VALUE_DIGITS}"
        );
    }

    Ok(())
}

fn pow_natural(base: Natural, exponent: Natural) -> Result<Natural> {
    if exponent == Natural::ZERO {
        if base == Natural::ZERO {
            bail!("0^0 is undefined");
        }
        return Ok(Natural::ONE);
    }

    let exp = natural_to_u64(&exponent)?;
    validate_pow(&base, exp)?;

    status_line(&format!(
        "evaluating power (~{} digits)...",
        estimate_pow_digits(&base, exp)
    ));

    Ok(base.pow(exp))
}

fn natural_to_u64(value: &Natural) -> Result<u64> {
    let max = Natural::from(u64::MAX);
    if value > &max {
        bail!("exponent too large");
    }

    value
        .to_string()
        .parse::<u64>()
        .map_err(|_| anyhow::anyhow!("exponent too large"))
}

pub fn looks_like_expression(input: &str) -> bool {
    input
        .chars()
        .any(|ch| matches!(ch, '+' | '-' | '*' | '/' | '^' | '(' | ')'))
}

pub fn parse_natural(input: &str) -> Result<Natural> {
    let trimmed = input.trim();
    if trimmed.is_empty() {
        bail!("input must not be empty");
    }

    if trimmed.starts_with('-') && !trimmed[1..].contains('-') && !looks_like_expression(trimmed) {
        bail!("value must be positive");
    }

    if !looks_like_expression(trimmed) {
        let value = Natural::from_str(trimmed)
            .map_err(|()| anyhow::anyhow!("invalid decimal integer"))?;
        return ensure_positive(value);
    }

    status_line(&format!("evaluating expression: {trimmed}"));

    let tokens = Lexer::new(trimmed).tokenize()?;
    let mut parser = Parser::new(tokens);
    let value = parser.parse_expr()?;
    parser.finish()?;
    ensure_positive(value)
}

fn ensure_positive(value: Natural) -> Result<Natural> {
    if value == Natural::ZERO {
        bail!("value must be greater than zero");
    }

    let digits = value.to_string().len() as u64;
    if digits > MAX_VALUE_DIGITS {
        bail!("value has {digits} digits; limit is {MAX_VALUE_DIGITS}");
    }

    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_plain_integer() {
        assert_eq!(parse_natural("27").unwrap(), Natural::from(27u32));
    }

    #[test]
    fn parses_power() {
        assert_eq!(
            parse_natural("2^54").unwrap(),
            Natural::from_str("18014398509481984").unwrap()
        );
    }

    #[test]
    fn parses_product() {
        assert_eq!(
            parse_natural("12340*248").unwrap(),
            Natural::from(3_060_320u32)
        );
    }

    #[test]
    fn parses_parentheses() {
        assert_eq!(parse_natural("(2+3)^4").unwrap(), Natural::from(625u32));
    }

    #[test]
    fn rejects_division_by_zero() {
        assert!(parse_natural("10/0").is_err());
    }

    #[test]
    fn rejects_non_positive_result() {
        assert!(parse_natural("1-2").is_err());
    }

    #[test]
    fn rejects_huge_power_quickly() {
        let err = parse_natural("935577^7777777").unwrap_err();
        assert!(err.to_string().contains("exponent"));
    }
}
