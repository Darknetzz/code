use crate::ast::{
    AndOrList, ChainOp, Pipeline, Program, RedirectSpec, SemicolonList, SimpleCommand, Stmt, Word,
};
use crate::lexer::Tok;
use anyhow::{anyhow, bail, Result};

pub fn parse_program(tokens: &[Tok]) -> Result<Program> {
    let mut p = Parser { t: tokens, i: 0 };
    let mut out = Vec::new();
    p.skip_sep();
    while !p.at_eof() {
        out.push(p.parse_stmt()?);
        p.skip_sep();
    }
    Ok(Program(out))
}

struct Parser<'a> {
    t: &'a [Tok],
    i: usize,
}

impl<'a> Parser<'a> {
    fn at_eof(&self) -> bool {
        matches!(self.peek(), Some(Tok::Eof) | None)
    }

    fn peek(&self) -> Option<&Tok> {
        self.t.get(self.i)
    }

    fn bump(&mut self) -> Option<Tok> {
        let tok = self.t.get(self.i).cloned()?;
        self.i += 1;
        Some(tok)
    }

    fn skip_sep(&mut self) {
        while matches!(self.peek(), Some(Tok::Semi) | Some(Tok::Newline)) {
            self.bump();
        }
    }

    fn skip_nl(&mut self) {
        while matches!(self.peek(), Some(Tok::Newline)) {
            self.bump();
        }
    }

    fn take_keyword(&mut self, kws: &[&str]) -> Option<String> {
        let mut j = self.i;
        while matches!(self.t.get(j), Some(Tok::Semi) | Some(Tok::Newline)) {
            j += 1;
        }
        match self.t.get(j)? {
            Tok::Word(w) => {
                let lit = w.single_literal()?.to_string();
                if kws.iter().any(|k| *k == lit) {
                    self.i = j + 1;
                    return Some(lit);
                }
                None
            }
            _ => None,
        }
    }

    fn peek_keyword_equals(&self, kw: &str) -> bool {
        let mut j = self.i;
        while matches!(self.t.get(j), Some(Tok::Semi) | Some(Tok::Newline)) {
            j += 1;
        }
        matches!(self.t.get(j), Some(Tok::Word(w)) if w.single_literal() == Some(kw))
    }

    fn consume_literal(&mut self, kw: &str) -> Result<()> {
        self.skip_sep();
        match self.peek() {
            Some(Tok::Word(w)) if w.single_literal() == Some(kw) => {
                self.bump();
                Ok(())
            }
            other => bail!("expected `{kw}`, found {other:?}"),
        }
    }

    fn starts_compound(&self) -> bool {
        let mut j = self.i;
        while matches!(self.t.get(j), Some(Tok::Semi) | Some(Tok::Newline)) {
            j += 1;
        }
        match self.t.get(j) {
            Some(Tok::Word(w)) => {
                if let Some(lit) = w.single_literal() {
                    return matches!(
                        lit,
                        "if" | "while" | "for"
                    ) || self.looks_like_fn_at(j);
                }
                false
            }
            _ => false,
        }
    }

    fn looks_like_fn_at(&self, j: usize) -> bool {
        match (self.t.get(j), self.t.get(j + 1), self.t.get(j + 2)) {
            (
                Some(Tok::Word(w)),
                Some(Tok::LParen),
                Some(Tok::RParen),
            ) => {
                let Some(name) = w.single_literal() else {
                    return false;
                };
                valid_name(name) && !reserved_word(name)
            }
            _ => false,
        }
    }

    fn parse_stmt(&mut self) -> Result<Stmt> {
        self.skip_sep();
        if self.at_eof() {
            bail!("unexpected EOF");
        }
        if self.looks_like_fn_at(self.keyword_cursor()) {
            return self.parse_function();
        }
        if self.peek_keyword_equals("if") {
            self.parse_if()
        } else if self.peek_keyword_equals("while") {
            self.parse_while()
        } else if self.peek_keyword_equals("for") {
            self.parse_for()
        } else {
            Ok(Stmt::SemicolonList(self.parse_standalone_semilist()?))
        }
    }

    fn keyword_cursor(&self) -> usize {
        let mut j = self.i;
        while matches!(self.t.get(j), Some(Tok::Semi) | Some(Tok::Newline)) {
            j += 1;
        }
        j
    }

    fn parse_standalone_semilist(&mut self) -> Result<SemicolonList> {
        let mut v = Vec::new();
        loop {
            self.skip_sep();
            if self.at_eof() || self.starts_compound() || self.looks_like_fn_at(self.keyword_cursor())
            {
                break;
            }
            v.push(self.parse_and_or()?);
            self.skip_sep();
            if self.at_eof() || self.starts_compound() || self.looks_like_fn_at(self.keyword_cursor())
            {
                break;
            }
            if !matches!(
                self.peek(),
                Some(Tok::Semi) | Some(Tok::Newline) | Some(Tok::Eof)
            ) {
                bail!("unexpected token after command: {:?}", self.peek());
            }
        }
        if v.is_empty() {
            bail!("empty statement");
        }
        Ok(SemicolonList(v))
    }

    /// Collect `AndOrList` segments until hitting one of `kws`, consuming that delimiter.
    fn parse_semicolon_until(&mut self, kws: &[&str]) -> Result<(SemicolonList, Option<String>)> {
        let mut v = Vec::new();
        loop {
            self.skip_sep();
            if let Some(stop) = self.take_keyword(kws) {
                return Ok((SemicolonList(v), Some(stop)));
            }
            if self.at_eof() {
                bail!(
                    "unexpected EOF expecting one of `{}` while parsing compound list",
                    kws.join("`, `")
                );
            }
            v.push(self.parse_and_or()?);
        }
    }

    fn parse_if(&mut self) -> Result<Stmt> {
        self.consume_literal("if")?;
        let (cond, _) = self.parse_semicolon_until(&["then"])?;
        let (then_branch, kw) = self.parse_semicolon_until(&["elif", "else", "fi"])?;

        let mut elifs = Vec::new();
        let mut kw = kw.ok_or_else(|| anyhow!("missing `if` terminator"))?;

        loop {
            match kw.as_str() {
                "elif" => {
                    let (c, _) = self.parse_semicolon_until(&["then"])?;
                    let (branch, nk) = self.parse_semicolon_until(&["elif", "else", "fi"])?;
                    elifs.push((c, branch));
                    kw = nk.ok_or_else(|| anyhow!("unterminated elif"))?;
                }
                "else" => {
                    let (else_part, nk) = self.parse_semicolon_until(&["fi"])?;
                    if nk.as_deref() != Some("fi") {
                        bail!("missing `fi` after `else` body (got {:?})", nk);
                    }
                    return Ok(Stmt::If {
                        cond,
                        then_part: then_branch,
                        elifs,
                        else_part: Some(else_part),
                    });
                }
                "fi" => {
                    return Ok(Stmt::If {
                        cond,
                        then_part: then_branch,
                        elifs,
                        else_part: None,
                    });
                }
                other => bail!("unexpected keyword `{other}` while parsing `if`"),
            }
        }
    }

    fn parse_while(&mut self) -> Result<Stmt> {
        self.consume_literal("while")?;
        let (cond, _) = self.parse_semicolon_until(&["do"])?;
        let (body, stop) = self.parse_semicolon_until(&["done"])?;
        if stop.as_deref() != Some("done") {
            bail!("expected `done`, got {:?}", stop);
        }
        Ok(Stmt::While { cond, body })
    }

    fn parse_for(&mut self) -> Result<Stmt> {
        self.consume_literal("for")?;
        self.skip_sep();
        let var = match self.peek() {
            Some(Tok::Word(w)) => {
                let n = w
                    .single_literal()
                    .ok_or_else(|| anyhow!("`for` variable must be a literal word"))?;
                self.bump();
                n.to_string()
            }
            other => bail!("expected variable after `for`, got {other:?}"),
        };
        if !valid_name(&var) {
            bail!("illegal variable name `{var}`");
        }
        self.consume_literal("in")?;
        let mut items = Vec::new();
        loop {
            self.skip_sep();
            match self.peek() {
                Some(Tok::Semi) => {
                    self.bump();
                    break;
                }
                Some(Tok::Word(_)) => items.push(self.expect_word()?),
                other => bail!("invalid token inside `for` list: {:?}", other),
            }
        }
        self.consume_literal("do")?;
        let (body, stop) = self.parse_semicolon_until(&["done"])?;
        if stop.as_deref() != Some("done") {
            bail!("missing `done` closing `for` loop (got {:?})", stop);
        }
        Ok(Stmt::For { var, items, body })
    }

    fn parse_function(&mut self) -> Result<Stmt> {
        self.skip_sep();
        let name = match self.peek() {
            Some(Tok::Word(w)) => {
                let n = w
                    .single_literal()
                    .ok_or_else(|| anyhow!("function names must be unquoted literals"))?;
                let n = n.to_string();
                self.bump();
                n
            }
            other => bail!("expected function name, got {other:?}"),
        };
        if reserved_word(&name) {
            bail!("`{name}` cannot be used as a function name");
        }
        match self.peek() {
            Some(Tok::LParen) => self.bump(),
            other => bail!("expected `(` after function name, got {other:?}"),
        };
        match self.peek() {
            Some(Tok::RParen) => self.bump(),
            other => bail!("expected `)` after `(` in function declaration, got {other:?}"),
        };
        self.skip_sep();
        match self.peek() {
            Some(Tok::LBrace) => self.bump(),
            other => bail!("expected `{{` to begin function body, got {other:?}"),
        };
        let body = self.parse_until_rcurly()?;
        Ok(Stmt::Function { name, body })
    }

    fn parse_until_rcurly(&mut self) -> Result<Vec<Stmt>> {
        let mut out = Vec::new();
        loop {
            self.skip_sep();
            if matches!(self.peek(), Some(Tok::RBrace)) {
                self.bump();
                break;
            }
            if self.at_eof() {
                bail!("unexpected EOF inside `{{ }}` block");
            }
            out.push(self.parse_stmt()?);
        }
        Ok(out)
    }

    fn parse_and_or(&mut self) -> Result<AndOrList> {
        let head = self.parse_pipeline()?;
        let mut tail = Vec::new();
        loop {
            self.skip_nl();
            match self.peek() {
                Some(Tok::AndAnd) => {
                    self.bump();
                    tail.push((ChainOp::And, self.parse_pipeline()?));
                }
                Some(Tok::PipePipe) => {
                    self.bump();
                    tail.push((ChainOp::Or, self.parse_pipeline()?));
                }
                _ => break,
            }
        }
        Ok(AndOrList { head, tail })
    }

    fn parse_pipeline(&mut self) -> Result<Pipeline> {
        let mut cmds = vec![self.parse_simple_command()?];
        loop {
            self.skip_nl();
            if matches!(self.peek(), Some(Tok::Pipe)) {
                self.bump();
                cmds.push(self.parse_simple_command()?);
            } else {
                break;
            }
        }
        self.skip_nl();
        let bg = matches!(self.peek(), Some(Tok::Amp)).then(|| {
            self.bump();
            true
        });
        Ok(Pipeline {
            cmds,
            background: bg.unwrap_or(false),
        })
    }

    fn parse_simple_command(&mut self) -> Result<SimpleCommand> {
        let mut assigns = Vec::new();
        let mut reds = Vec::new();
        let mut argv = Vec::new();

        loop {
            self.skip_nl();
            let allow_amp = !argv.is_empty() || !assigns.is_empty() || !reds.is_empty();
            if self.simple_cmd_terminal(allow_amp).is_some() {
                break;
            }
            match self.peek() {
                Some(Tok::Lt { .. } | Tok::Gt { .. } | Tok::Dup { .. }) => {
                    reds.push(self.parse_redirect()?);
                }
                Some(Tok::Word(w)) => {
                    let w = (*w).clone();
                    self.bump();
                    if argv.is_empty() {
                        if let Some(asg) = split_assignment(&w) {
                            assigns.push(asg);
                            continue;
                        }
                    }
                    argv.push(w);
                    break;
                }
                other => bail!("unexpected token `{other:?}` in command prefix"),
            }
        }

        loop {
            self.skip_nl();
            let allow_amp = !argv.is_empty() || !assigns.is_empty() || !reds.is_empty();
            if let Some(stop) = self.simple_cmd_terminal(allow_amp) {
                if stop == CmdTerm::Amp {
                    // pipeline parses background; don't consume '&' here.
                }
                break;
            }
            match self.peek() {
                Some(Tok::Lt { .. } | Tok::Gt { .. } | Tok::Dup { .. }) => {
                    reds.push(self.parse_redirect()?);
                }
                Some(Tok::Word(_)) => argv.push(self.expect_word()?),
                Some(other) => bail!("unsupported token `{other:?}`"),
                None => bail!("unexpected EOF parsing command arguments"),
            }
        }

        Ok(SimpleCommand {
            assigns,
            argv,
            redirects: reds,
        })
    }

    fn simple_cmd_terminal(&self, saw_cmd: bool) -> Option<CmdTerm> {
        match self.peek() {
            Some(
                Tok::Semi
                | Tok::Newline
                | Tok::Pipe
                | Tok::AndAnd
                | Tok::PipePipe
                | Tok::RParen
                | Tok::RBrace
                | Tok::Eof,
            ) => Some(CmdTerm::Break),
            Some(Tok::Amp) if saw_cmd => Some(CmdTerm::Amp),
            _ => None,
        }
    }

    fn parse_redirect(&mut self) -> Result<RedirectSpec> {
        match self
            .bump()
            .ok_or_else(|| anyhow!("internal parser error redirect"))?
            .clone()
        {
            Tok::Lt { fd } => Ok(RedirectSpec::OpenRead {
                fd: fd.unwrap_or(0),
                target: self.expect_word()?,
            }),
            Tok::Gt { fd, append } => Ok(RedirectSpec::OpenWrite {
                fd: fd.unwrap_or(1),
                truncate: !append,
                target: self.expect_word()?,
            }),
            Tok::Dup { src, dst } => Ok(RedirectSpec::DupFd {
                fd: src,
                target_fd: dst,
            }),
            other => bail!("unexpected token as redirect {:?}", other),
        }
    }

    fn expect_word(&mut self) -> Result<Word> {
        match self.bump() {
            Some(Tok::Word(w)) => Ok(w),
            other => bail!("expected word token, got {other:?}"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum CmdTerm {
    Break,
    Amp,
}

fn valid_name(name: &str) -> bool {
    let mut it = name.chars();
    let Some(first) = it.next() else { return false };
    if !(first.is_ascii_alphabetic() || first == '_') {
        return false;
    }
    it.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

fn reserved_word(s: &str) -> bool {
    matches!(
        s,
        "if" | "then" | "else" | "elif" | "fi" | "while" | "do" | "done" | "for" | "in"
    )
}

fn split_assignment(word: &Word) -> Option<(String, Word)> {
    let parts = &word.0;
    match parts.first() {
        Some(crate::ast::WordPart::Literal(head)) => {
            if let Some(eq) = head.find('=') {
                let name = head[..eq].to_string();
                if !valid_name(&name) {
                    return None;
                }
                let rest = head[eq + 1..].to_string();
                let mut tail = Vec::new();
                if !rest.is_empty() {
                    tail.push(crate::ast::WordPart::Literal(rest));
                }
                tail.extend(parts.iter().skip(1).cloned());
                return Some((name, Word(tail)));
            }
            None
        }
        _ => None,
    }
}
