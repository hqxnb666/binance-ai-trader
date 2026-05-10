from __future__ import annotations

from diagnostics.network import REGION_RESTRICTED, classify_http_status


def test_restricted_location_text_classified_region_restricted() -> None:
    assert (
        classify_http_status(
            503,
            "Service unavailable from a restricted location according to b. Eligibility",
        )
        == REGION_RESTRICTED
    )


def test_http_451_classified_region_restricted() -> None:
    assert classify_http_status(451, "Unavailable for legal reasons") == REGION_RESTRICTED

