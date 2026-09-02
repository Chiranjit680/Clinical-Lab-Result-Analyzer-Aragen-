from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class LabRecord(BaseModel):
    """Schema for one incoming lab row, matching the Kaggle dataset's columns.

    Only test_name/result are required so a batch with a partially-bad row
    doesn't fail validation for the whole request — agent.py validates each
    row against this model individually and routes failures into `errors[]`.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore", str_strip_whitespace=True)

    test_name: str = Field(alias="Test_Name", min_length=1)
    result: float = Field(alias="Result")
    unit: Optional[str] = Field(default=None, alias="Unit")
    reference: Optional[str] = Field(default=None, alias="Reference")
    status: Optional[str] = Field(default=None, alias="Status")
    comment: Optional[str] = Field(default=None, alias="Comment")
    min_refer: Optional[float] = Field(default=None, alias="Min_Refer")
    max_refer: Optional[float] = Field(default=None, alias="Max_Refer")
    unit_desc: Optional[str] = Field(default=None, alias="Unit_Desc")
    recommended_followup: Optional[str] = Field(default=None, alias="Recommended_Followup")


class AnalyzeLabsRequest(BaseModel):
    patient_id: Optional[str] = None
    labs: List[Dict[str, Any]]


class LabResult(BaseModel):
    test_name: str
    value: float
    unit: str
    status: str
    reference_range: Optional[str] = None
    deviation: Optional[str] = None
    explanation: str = ""
    next_steps: str = ""
    source_status: Optional[str] = None
    source_followup: Optional[str] = None


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
