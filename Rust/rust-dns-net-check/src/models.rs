use serde::Serialize;
use serde_json::{Map, Value};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum CheckStatus {
    Pass,
    Fail,
    Warn,
}

impl CheckStatus {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Pass => "pass",
            Self::Fail => "fail",
            Self::Warn => "warn",
        }
    }
}

#[derive(Debug, Clone)]
pub struct CheckResult {
    pub name: String,
    pub target: String,
    pub status: CheckStatus,
    pub latency_ms: Option<f64>,
    pub details: Map<String, Value>,
    pub error: Option<String>,
    pub hint: Option<String>,
}

impl CheckResult {
    pub fn pass(
        name: impl Into<String>,
        target: impl Into<String>,
        latency_ms: f64,
        details: Map<String, Value>,
    ) -> Self {
        Self {
            name: name.into(),
            target: target.into(),
            status: CheckStatus::Pass,
            latency_ms: Some(latency_ms),
            details,
            error: None,
            hint: None,
        }
    }

    pub fn fail(
        name: impl Into<String>,
        target: impl Into<String>,
        latency_ms: Option<f64>,
        error: impl Into<String>,
        hint: impl Into<String>,
        details: Map<String, Value>,
    ) -> Self {
        Self {
            name: name.into(),
            target: target.into(),
            status: CheckStatus::Fail,
            latency_ms,
            details,
            error: Some(error.into()),
            hint: Some(hint.into()),
        }
    }

    pub fn to_json(&self) -> Map<String, Value> {
        let mut map = Map::new();
        map.insert("name".into(), Value::String(self.name.clone()));
        map.insert("target".into(), Value::String(self.target.clone()));
        map.insert(
            "status".into(),
            Value::String(self.status.as_str().into()),
        );
        if let Some(latency_ms) = self.latency_ms {
            map.insert("latency_ms".into(), Value::from(latency_ms));
        }
        map.insert("details".into(), Value::Object(self.details.clone()));
        if let Some(error) = &self.error {
            map.insert("error".into(), Value::String(error.clone()));
        }
        if let Some(hint) = &self.hint {
            map.insert("hint".into(), Value::String(hint.clone()));
        }
        map
    }
}

pub fn details_map() -> Map<String, Value> {
    Map::new()
}

pub fn detail_str(key: &str, value: impl Into<String>, details: &mut Map<String, Value>) {
    details.insert(key.into(), Value::String(value.into()));
}

pub fn detail_bool(key: &str, value: bool, details: &mut Map<String, Value>) {
    details.insert(key.into(), Value::Bool(value));
}

pub fn detail_f64(key: &str, value: f64, details: &mut Map<String, Value>) {
    details.insert(key.into(), Value::from(value));
}

pub fn detail_strings(key: &str, values: &[String], details: &mut Map<String, Value>) {
    details.insert(
        key.into(),
        Value::Array(values.iter().cloned().map(Value::String).collect()),
    );
}
