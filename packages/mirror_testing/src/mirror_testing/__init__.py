"""Mirror Testing – shared contract-testing utilities."""

from mirror_testing.base import BaseContract

try:
    from mirror_testing.legal_sites import (
        LEGAL_SITES,
        LiveFetchResult,
        LegalSite,
        tier1_sites,
        tier2_sites,
        legal_sites,
        assert_ok,
        assert_html,
        assert_json,
    )
except Exception:
    # Live-site fixtures are optional — ignore import errors if deps missing
    pass

__all__ = ["BaseContract"]
