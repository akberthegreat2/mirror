"""Capability manifest for Transform."""

from mirror_core.extensions.models import CapabilityManifest

from mirror_transform.models import TransformRequest, TransformResult
from mirror_transform.protocol import Transformer

capability = CapabilityManifest(
    name="transform",
    api_version="1.0.0",
    protocol=Transformer,
    request_model=TransformRequest,
    result_model=TransformResult,
    runner="mirror_transform.runner:transform_step",
    metadata={"summary": "Reshape a resolved value into a target model between steps"},
)
