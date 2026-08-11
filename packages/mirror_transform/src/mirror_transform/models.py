"""Typed models for the Transform capability."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TransformRequest(BaseModel):
    """Reshape one resolved value into a target model declared by the pipeline.

    ``value`` is the payload of a previous step (already resolved by the
    executor). ``mapping`` declares how each field of the target model is
    sourced: dotted paths are read from ``value``, other strings and values
    are treated as literals. ``metadata`` is merged into the constructed
    object's ``metadata`` field when present.
    """

    value: Any = Field(default=None, description="Input payload to reshape.")
    output_type: str = Field(
        ...,
        description="Import path of the target model, e.g. 'mirror_chunk.models:ChunkDocument'.",
    )
    mapping: dict[str, Any] = Field(
        default_factory=dict,
        description="Target field -> source. A source that resolves to a path into ``value`` is extracted; anything else is a literal.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Literal metadata merged into the constructed object.",
    )


class TransformResult(BaseModel):
    """The object constructed by a Transform step."""

    value: Any = Field(default=None, description="The constructed target object.")
    produced_type: str = Field(default="", description="Import path of the produced model.")
