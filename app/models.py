from enum import Enum

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime

from config import SUPPORTED_WORLDS, DEFAULT_WORLD


class CPOState(str, Enum):
    PROPOSED = "proposed"
    ATTESTED = "attested"
    VERIFIED = "verified"
    CONTESTED = "contested"
    INVALID = "invalid"


class PeerNode(BaseModel):
    node_id: str
    public_key: str
    url: str
    announced_at: Optional[datetime] = None


class Attestation(BaseModel):
    node_id: str
    public_key: str
    cpo_hash: str
    verdict: bool
    signature: str
    timestamp: datetime


class ExecutionSpec(BaseModel):
    runtime: str = "python"
    # If None, the executor picks the image based on CPO.world
    image: Optional[str] = None
    constraints: Dict[str, Any] = Field(
        default_factory=lambda: {"timeout": 10, "memory_mb": 128}
    )


class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: Optional[float] = None


class CPO(BaseModel):
    cpo_id: Optional[str] = None
    world: str = DEFAULT_WORLD
    claim: str
    code: str
    execution_spec: ExecutionSpec = Field(default_factory=ExecutionSpec)
    result: Optional[ExecutionResult] = None
    parents: List[str] = Field(default_factory=list)
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    content_hash: Optional[str] = None
    signature: Optional[str] = None
    signer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("world")
    @classmethod
    def validate_world(cls, v: str) -> str:
        if v not in SUPPORTED_WORLDS:
            raise ValueError(
                f"Unsupported world '{v}'. Must be one of: {sorted(SUPPORTED_WORLDS)}"
            )
        return v
