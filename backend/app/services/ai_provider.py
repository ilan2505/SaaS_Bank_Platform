"""Provider-agnostic interface for AI-based PDF extraction.

Concrete providers (Anthropic, OpenAI, Gemini, ...) implement `AIProvider`.
The rest of the application only depends on this interface, never on a
specific SDK, so swapping or adding a provider does not touch the ingestion
or validation logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExtractionResult:
    records: list[dict] = field(default_factory=list)
    error: str | None = None


class AIProvider(ABC):
    @abstractmethod
    def extract(self, pdf_bytes: bytes, filename: str) -> ExtractionResult:
        """Extract financial_record-shaped dicts from a PDF's content.

        Must never raise for provider-side failures (auth, network, timeout,
        malformed response): those are reported via `ExtractionResult.error`
        so the caller can persist a NEEDS_REVIEW record instead of crashing
        the upload.
        """
        raise NotImplementedError
