use crate::ast::{Word, WordPart};

#[derive(Debug, Clone, PartialEq)]
pub enum Tok {
    Eof,
    Newline,
    Semi,
    Amp,
    Pipe,
    AndAnd,
    PipePipe,
    LParen,
    RParen,
    LBrace,
    RBrace,
    /// Default fd 0 if None
    Lt { fd: Option<i32> },
    /// Default fd 1 if None
    Gt { fd: Option<i32>, append: bool },
    Dup { src: i32, dst: i32 },
    Word(Word),
}

#[derive(Debug, thiserror::Error)]
pub enum LexError {
    #[error("unterminated quote")]
    UnterminatedQuote,
    #[error("invalid duplication redirect")]
    InvalidDupRedirect,
    #[error("command substitution $(...) is not supported yet")]
    CommandSubstitutionUnsupported,
}

pub struct Lexer {
    chars: Vec<char>,
    i: usize,
}

impl Lexer {
    pub fn new(src: &str) -> Self {
        Self {
            chars: src.chars().collect(),
            i: 0,
        }
    }

    pub fn lex_all(mut self) -> Result<Vec<Tok>, LexError> {
        let mut out = Vec::new();
        loop {
            self.skip_hspace();
            let Some(c) = self.peek() else {
                out.push(Tok::Eof);
                break;
            };

            match c {
                '\n' => {
                    self.bump();
                    out.push(Tok::Newline);
                }
                '#' => self.skip_comment(),
                ';' => {
                    self.bump();
                    out.push(Tok::Semi);
                }
                '|' => {
                    self.bump();
                    out.push(if self.peek() == Some('|') {
                        self.bump();
                        Tok::PipePipe
                    } else {
                        Tok::Pipe
                    });
                }
                '&' => {
                    self.bump();
                    out.push(if self.peek() == Some('&') {
                        self.bump();
                        Tok::AndAnd
                    } else {
                        Tok::Amp
                    });
                }
                '(' => {
                    self.bump();
                    out.push(Tok::LParen);
                }
                ')' => {
                    self.bump();
                    out.push(Tok::RParen);
                }
                '{' => {
                    self.bump();
                    out.push(Tok::LBrace);
                }
                '}' => {
                    self.bump();
                    out.push(Tok::RBrace);
                }
                '<' => {
                    self.bump();
                    out.push(Tok::Lt { fd: None });
                }
                '>' => {
                    self.bump();
                    let append = if self.peek() == Some('>') {
                        self.bump();
                        true
                    } else {
                        false
                    };
                    out.push(Tok::Gt {
                        fd: None,
                        append,
                    });
                }
                '"' | '\'' => {
                    out.push(Tok::Word(self.read_word()?));
                }
                _ => {
                    if let Some(tok) = self.try_digit_redirect()? {
                        out.push(tok);
                    } else {
                        out.push(Tok::Word(self.read_word()?));
                    }
                }
            }
        }
        Ok(out)
    }

    /// If input starts like `12>file` or `3>&2`, consume and return redirect token; otherwise restore cursor.
    fn try_digit_redirect(&mut self) -> Result<Option<Tok>, LexError> {
        let start = self.i;
        if !self.peek().is_some_and(|c| c.is_ascii_digit()) {
            return Ok(None);
        }
        while self.peek().is_some_and(|c| c.is_ascii_digit()) {
            self.bump();
        }
        let num_start = start;
        let num_end = self.i;
        let n: String = self.chars[num_start..num_end].iter().collect();
        let fd: i32 = n.parse().unwrap_or(1);

        match self.peek() {
            Some('<') => {
                self.bump();
                Ok(Some(Tok::Lt { fd: Some(fd) }))
            }
            Some('>') => {
                self.bump();
                let append = if self.peek() == Some('>') {
                    self.bump();
                    true
                } else {
                    false
                };
                if self.peek() == Some('&') {
                    self.bump();
                    let ds = self.i;
                    if !self.peek().is_some_and(|c| c.is_ascii_digit()) {
                        self.i = start;
                        return Ok(None);
                    }
                    while self.peek().is_some_and(|c| c.is_ascii_digit()) {
                        self.bump();
                    }
                    let de = self.i;
                    let dst_s: String = self.chars[ds..de].iter().collect();
                    let dst: i32 = dst_s
                        .parse()
                        .map_err(|_| LexError::InvalidDupRedirect)?;
                    Ok(Some(Tok::Dup { src: fd, dst }))
                } else {
                    Ok(Some(Tok::Gt {
                        fd: Some(fd),
                        append,
                    }))
                }
            }
            _ => {
                self.i = start;
                Ok(None)
            }
        }
    }

    fn peek(&self) -> Option<char> {
        self.chars.get(self.i).copied()
    }

    fn bump(&mut self) -> Option<char> {
        let c = self.peek()?;
        self.i += 1;
        Some(c)
    }

    fn skip_hspace(&mut self) {
        while self
            .peek()
            .is_some_and(|c| c == ' ' || c == '\t' || c == '\r')
        {
            self.bump();
        }
    }

    fn skip_comment(&mut self) {
        while let Some(c) = self.peek() {
            if c == '\n' {
                break;
            }
            self.bump();
        }
    }

    fn read_word(&mut self) -> Result<Word, LexError> {
        let mut parts: Vec<WordPart> = Vec::new();
        let mut lit = String::new();

        #[derive(Clone, Copy)]
        enum Q {
            D,
            S,
        }

        fn flush(lit: &mut String, parts: &mut Vec<WordPart>) {
            if lit.is_empty() {
                return;
            }
            parts.push(WordPart::Literal(std::mem::take(lit)));
        }

        fn push_var(parts: &mut Vec<WordPart>, lit: &mut String, name: impl Into<String>) {
            flush(lit, parts);
            parts.push(WordPart::Var(name.into()));
        }

        fn read_quoted(lx: &mut Lexer, parts: &mut Vec<WordPart>, lit: &mut String, q: Q) -> Result<(), LexError> {
            loop {
                let Some(c) = lx.peek() else {
                    return Err(LexError::UnterminatedQuote);
                };
                match q {
                    Q::S => match c {
                        '\'' => {
                            lx.bump();
                            return Ok(());
                        }
                        _ => {
                            lx.bump();
                            lit.push(c);
                        }
                    },
                    Q::D => match c {
                        '"' => {
                            lx.bump();
                            return Ok(());
                        }
                        '\\' => {
                            lx.bump();
                            match lx.peek() {
                                Some('\n') => {
                                    lx.bump();
                                }
                                Some(ch @ ('$' | '`' | '"' | '\\')) => {
                                    lx.bump();
                                    lit.push(ch);
                                }
                                Some(ch) => {
                                    lx.bump();
                                    lit.push(ch);
                                }
                                None => lit.push('\\'),
                            }
                        }
                        '$' => {
                            lx.bump();
                            if lx.peek() == Some('(') {
                                return Err(LexError::CommandSubstitutionUnsupported);
                            }
                            if let Some(name) = lx.param_name(lit)? {
                                if name.is_empty() {
                                    lit.push('$');
                                } else {
                                    push_var(parts, lit, name);
                                }
                            } else {
                                lit.push('$');
                            }
                        }
                        _ => {
                            lx.bump();
                            lit.push(c);
                        }
                    },
                }
            }
        }

        loop {
            let Some(c) = self.peek() else {
                break;
            };
            match c {
                '"' => {
                    self.bump();
                    read_quoted(self, &mut parts, &mut lit, Q::D)?;
                }
                '\'' => {
                    self.bump();
                    read_quoted(self, &mut parts, &mut lit, Q::S)?;
                }
                '|' | '&' | ';' | '(' | ')' | '{' | '}' | '#' | '<' | '>' => break,
                '\n' => break,
                ' ' | '\t' | '\r' => break,
                '\\' => {
                    self.bump();
                    match self.peek() {
                        None => lit.push('\\'),
                        Some('\n') => {
                            self.bump();
                        }
                        Some(ch) => {
                            self.bump();
                            lit.push(ch);
                        }
                    }
                }
                '$' => {
                    self.bump();
                    if self.peek() == Some('(') {
                        return Err(LexError::CommandSubstitutionUnsupported);
                    }
                    if let Some(name) = self.param_name(&mut lit)? {
                        if name.is_empty() {
                            lit.push('$');
                        } else {
                            push_var(&mut parts, &mut lit, name);
                        }
                    } else {
                        lit.push('$');
                    }
                }
                _ => {
                    self.bump();
                    lit.push(c);
                }
            }
        }

        flush(&mut lit, &mut parts);
        Ok(Word(parts))
    }

    fn param_name(
        &mut self,
        lit: &mut String,
    ) -> Result<Option<String>, LexError> {
        let Some(c) = self.peek() else {
            return Ok(None);
        };
        match c {
            '{' => {
                self.bump();
                let mut name = String::new();
                loop {
                    let Some(ch) = self.peek() else {
                        return Err(LexError::UnterminatedQuote);
                    };
                    if ch == '}' {
                        self.bump();
                        break;
                    }
                    if ch.is_alphanumeric() || ch == '_' || ch == '?' || ch == '#' {
                        name.push(ch);
                        self.bump();
                    } else {
                        // invalid — treat as literal sequence
                        lit.push('{');
                        lit.push_str(&name);
                        return Ok(None);
                    }
                }
                Ok(Some(name))
            }
            '?' => {
                self.bump();
                Ok(Some("?".into()))
            }
            '$' => {
                self.bump();
                Ok(Some("$".into()))
            }
            '0'..='9' => {
                let mut n = String::new();
                while self.peek().is_some_and(|ch| ch.is_ascii_digit() || ch == '#') {
                    if self.peek() == Some('#') && !n.is_empty() {
                        break;
                    }
                    n.push(self.bump().unwrap());
                }
                if n.is_empty() {
                    Ok(None)
                } else {
                    Ok(Some(n))
                }
            }
            ch if ch.is_alphabetic() || ch == '_' => {
                let mut name = String::new();
                name.push(self.bump().unwrap());
                while self.peek().is_some_and(|ch| ch.is_alphanumeric() || ch == '_') {
                    name.push(self.bump().unwrap());
                }
                Ok(Some(name))
            }
            '(' => Ok(None),
            _ => Ok(None),
        }
    }
}
