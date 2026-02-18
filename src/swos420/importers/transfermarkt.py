"""Transfermarkt adapter — economics overlay (STUB).

This adapter will provide real market values, contract expiry, transfer history,
and nationality flags from Transfermarkt data (via scraper or Kaggle dump).

Currently a STUB — interface is defined, actual scraping logic is deferred.
The HybridImporter skips this source gracefully if it raises NotImplementedError.
"""

from __future__ import annotations

from swos420.importers.base import BaseImporter, RawPlayerRecord, RawTeamRecord


class TransfermarktAdapter(BaseImporter):
    """Transfermarkt data adapter — STUB implementation.

    TODO (Phase 2):
    - Integrate dcaribou/transfermarkt-scraper Python lib
    - Or parse weekly Kaggle dump CSV
    - Provide: market values, contract expiry, transfer history, nationality flags
    """

    source_name = "transfermarkt"

    def load(self, source_path: str) -> list[RawPlayerRecord]:
        """Load players from Transfermarkt data.

        Not yet implemented. The HybridImporter handles this gracefully
        by falling back to Sofifa values.
        """
        raise NotImplementedError(
            "TransfermarktAdapter is not yet implemented. "
            "Use SofifaCSVAdapter as primary source. "
            "To contribute, implement scraping via dcaribou/transfermarkt-scraper "
            "or parse a Kaggle CSV dump."
        )

    def get_teams(self, source_path: str) -> list[RawTeamRecord]:
        """Load teams from Transfermarkt data — not yet implemented."""
        raise NotImplementedError(
            "TransfermarktAdapter.get_teams() is not yet implemented."
        )
