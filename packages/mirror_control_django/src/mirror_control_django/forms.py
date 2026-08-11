"""Admin forms for Mirror control-plane models."""

from __future__ import annotations

from typing import ClassVar

from django import forms
from mirror_control.service import default_blob_store, deserialize_pipeline_definition
from mirror_core.pipeline import Pipeline as CorePipeline

from mirror_control_django import models


class PipelineVersionForm(forms.ModelForm):
    """Edit a pipeline version through a blob-backed text area."""

    definition_text = forms.CharField(
        label="Definition",
        widget=forms.Textarea(attrs={"rows": 24, "cols": 100}),
        required=True,
    )

    class Meta:
        model = models.PipelineVersion
        fields: ClassVar[list[str]] = [
            "pipeline_id",
            "version",
            "definition_ref",
            "definition_hash",
            "definition_format",
            "metadata",
        ]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        blob_store = default_blob_store()
        if self.instance.pk and self.instance.definition_ref:
            payload = blob_store.get_bytes(self.instance.definition_ref)
            if payload is not None:
                self.fields["definition_text"].initial = payload.decode("utf-8")
        else:
            self.fields["definition_text"].initial = CorePipeline(id="pipeline", steps=[]).model_dump_json(indent=2)
        if self.instance.pk:
            try:
                pipeline = models.Pipeline.objects.get(pk=self.instance.pipeline_id)
            except models.Pipeline.DoesNotExist:
                pipeline = None
            if pipeline is not None and pipeline.is_read_only:
                self.fields["definition_text"].disabled = True

    def clean_definition_text(self) -> str:
        value = self.cleaned_data["definition_text"]
        try:
            deserialize_pipeline_definition(value.encode("utf-8"))
        except Exception as exc:  # pragma: no cover - validation path
            raise forms.ValidationError(str(exc)) from exc
        return value
