//! Abstract syntax for Darkshell / `dsh` (Bash-inspired subset).
#![allow(dead_code)]

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WordPart {
    Literal(String),
    Var(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Word(pub Vec<WordPart>);

impl Word {
    pub fn literal(s: impl Into<String>) -> Self {
        Self(vec![WordPart::Literal(s.into())])
    }

    pub fn single_literal(&self) -> Option<&str> {
        match self.0.as_slice() {
            [WordPart::Literal(s)] => Some(s.as_str()),
            _ => None,
        }
    }

    pub fn merge_literals(&self) -> String {
        let mut out = String::new();
        for p in &self.0 {
            if let WordPart::Literal(s) = p {
                out.push_str(s);
            }
        }
        out
    }

    pub fn looks_like_keyword(&self, kw: &str) -> bool {
        self.single_literal().is_some_and(|s| s == kw)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RedirectSpec {
    OpenRead { fd: i32, target: Word },
    OpenWrite { fd: i32, truncate: bool, target: Word },
    DupFd { fd: i32, target_fd: i32 },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SimpleCommand {
    pub assigns: Vec<(String, Word)>,
    pub argv: Vec<Word>,
    pub redirects: Vec<RedirectSpec>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pipeline {
    pub cmds: Vec<SimpleCommand>,
    pub background: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SemicolonList(pub Vec<AndOrList>);

impl SemicolonList {
    pub fn singleton(and_or: AndOrList) -> Self {
        Self(vec![and_or])
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChainOp {
    And,
    Or,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AndOrList {
    pub head: Pipeline,
    pub tail: Vec<(ChainOp, Pipeline)>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Stmt {
    SemicolonList(SemicolonList),
    If {
        cond: SemicolonList,
        then_part: SemicolonList,
        elifs: Vec<(SemicolonList, SemicolonList)>,
        else_part: Option<SemicolonList>,
    },
    While {
        cond: SemicolonList,
        body: SemicolonList,
    },
    For {
        var: String,
        items: Vec<Word>,
        body: SemicolonList,
    },
    Function {
        name: String,
        body: Vec<Stmt>,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Program(pub Vec<Stmt>);
