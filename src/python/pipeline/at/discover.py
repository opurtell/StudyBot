"""Playwright-based site discovery for AT CPG portal.

This module probes the Ambulance Tasmania Clinical Practice Guidelines
site at https://cpg.ambulance.tas.gov.au to extract the navigation structure,
enumerate guidelines, and discover medicine monographs.

The AT CPG site is an Angular + Ionic SPA, architecturally similar to the
ACTAS CMG site. Discovery uses Playwright to render the SPA and extract
the navigation tree and guideline metadata.
"""

from .models import ATDiscoveryResult


def discover_site(output_dir: str | None = None) -> ATDiscoveryResult:
    """Discover the AT CPG site structure and enumerate guidelines.

    This is a stub implementation that returns an empty discovery result.
    The full implementation will use Playwright to:

    1. Navigate to https://cpg.ambulance.tas.gov.au/tabs/guidelines
    2. Dismiss any disclaimer modal
    3. Remove level selector if present
    4. Extract the navigation tree
    5. Enumerate guideline links with CPG codes
    6. Navigate to /tabs/medicines
    7. Capture medicine names and D-codes

    Args:
        output_dir: Optional directory to save discovery results

    Returns:
        ATDiscoveryResult with discovered guidelines and medicines
    """
    # Stub implementation - returns empty result
    # Full implementation will use Playwright to extract site structure
    return ATDiscoveryResult()
