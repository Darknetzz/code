use serde::Serialize;
use serde_json::Map;

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
    pub id: String,
    pub label: String,
    pub status: CheckStatus,
    pub required: bool,
    pub version: Option<String>,
    pub detail: Option<String>,
    pub hint: Option<String>,
}

impl CheckResult {
    pub fn pass(
        id: impl Into<String>,
        label: impl Into<String>,
        required: bool,
        version: Option<String>,
        detail: Option<String>,
    ) -> Self {
        Self {
            id: id.into(),
            label: label.into(),
            status: CheckStatus::Pass,
            required,
            version,
            detail,
            hint: None,
        }
    }

    pub fn fail(
        id: impl Into<String>,
        label: impl Into<String>,
        required: bool,
        detail: impl Into<String>,
        hint: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            label: label.into(),
            status: CheckStatus::Fail,
            required,
            version: None,
            detail: Some(detail.into()),
            hint: Some(hint.into()),
        }
    }

    pub fn warn(
        id: impl Into<String>,
        label: impl Into<String>,
        detail: impl Into<String>,
        hint: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            label: label.into(),
            status: CheckStatus::Warn,
            required: false,
            version: None,
            detail: Some(detail.into()),
            hint: Some(hint.into()),
        }
    }

    pub fn to_json(&self) -> Map<String, serde_json::Value> {
        let mut map = Map::new();
        map.insert("id".into(), self.id.clone().into());
        map.insert("label".into(), self.label.clone().into());
        map.insert("status".into(), self.status.as_str().into());
        map.insert("required".into(), self.required.into());
        if let Some(version) = &self.version {
            map.insert("version".into(), version.clone().into());
        }
        if let Some(detail) = &self.detail {
            map.insert("detail".into(), detail.clone().into());
        }
        if let Some(hint) = &self.hint {
            map.insert("hint".into(), hint.clone().into());
        }
        map
    }
}
