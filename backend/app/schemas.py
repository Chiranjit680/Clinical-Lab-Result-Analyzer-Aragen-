from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LabRecord(BaseModel):
    """Schema for one incoming lab row, matching the Kaggle dataset's columns.

    Only test_name/result are required so a batch with a partially-bad row
    doesn't fail validation for the whole request — graph.py validates each
    row against this model individually and routes failures into `errors[]`.

    `result` may be numeric (28.9) or qualitative ("Negatif", "1+", "Normal") —
    roughly half the source dataset is urine-strip rows with qualitative values
    and blank Min/Max_Reference, so both forms are accepted here and dispatched
    to different classifier tools downstream.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    date: Optional[str] = Field(default=None, alias="Date")
    test_name: str = Field(alias="Test_Name", min_length=1)
    result: Union[float, str] = Field(alias="Result")
    unit: Optional[str] = Field(default=None, alias="Unit")
    reference_range: Optional[str] = Field(default=None, alias="Reference_Range")
    status: Optional[str] = Field(default=None, alias="Status")
    comment: Optional[str] = Field(default=None, alias="Comment")
    min_reference: Optional[float] = Field(default=None, alias="Min_Reference")
    max_reference: Optional[float] = Field(default=None, alias="Max_Reference")
    unit_description: Optional[str] = Field(default=None, alias="Unit_Description")
    recommended_followup: Optional[str] = Field(default=None, alias="Recommended_Followup")

    # Filled in by the graph's translate node (source data is Turkish).
    test_name_en: Optional[str] = None
    status_en: Optional[str] = None
    comment_en: Optional[str] = None
    recommended_followup_en: Optional[str] = None

    @field_validator("result", mode="before")
    @classmethod
    def _coerce_result(cls, v: Any) -> Union[float, str]:
        """Numeric where possible, otherwise keep the qualitative string."""
        if v is None:
            raise ValueError("missing")
        if isinstance(v, (int, float)):
            return float(v)
        text = str(v).strip()
        if not text:
            raise ValueError("missing")
        try:
            # Accept comma decimal separators (e.g. "1,02") as well as "1.02".
            return float(text.replace(",", "."))
        except ValueError:
            return text

    @field_validator("min_reference", "max_reference", mode="before")
    @classmethod
    def _blank_to_none(cls, v: Any) -> Any:
        """Qualitative rows leave these columns empty."""
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, str):
            return v.strip().replace(",", ".")
        return v

    @property
    def is_qualitative(self) -> bool:
        return isinstance(self.result, str)


class AnalyzeLabsRequest(BaseModel):
    patient_id: Optional[str] = None
    labs: List[Dict[str, Any]]


class Source(BaseModel):
    title: str = ""
    url: str = ""


class LabResult(BaseModel):
    test_name: str
    value: Union[float, str]
    unit: str
    status: str
    reference_range: Optional[str] = None
    deviation: Optional[str] = None
    explanation: str = ""
    next_steps: str = ""
    source_status: Optional[str] = None
    source_followup: Optional[str] = None
    # Original (untranslated) values kept alongside, so a reviewer can always
    # trace a translated label back to what the source record actually said.
    test_name_original: Optional[str] = None
    source_comment: Optional[str] = None
    urgent: Optional[bool] = None
    sources: List[Source] = []
    source_type: Optional[str] = None


class ErrorItem(BaseModel):
    test_name: Optional[str] = None
    error: str


class Summary(BaseModel):
    critical: int = 0
    warning: int = 0
    normal: int = 0
    unknown: int = 0


class AnalyzeLabsResponse(BaseModel):
    summary: Summary
    results: Dict[str, List[LabResult]]
    errors: List[ErrorItem]
    # Checkpoint thread the run is parked on; the client passes this to
    # /ws/chat/{thread_id} to ask follow-up questions about these results.
    thread_id: Optional[str] = None
