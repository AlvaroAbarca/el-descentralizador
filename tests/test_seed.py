from __future__ import annotations

from el_descentralizador.db.models.source import SourceKind
from el_descentralizador.server.seed import load_catalog_rows


def test_seed_catalog_reads_csv() -> None:
    from el_descentralizador.lib.settings import get_settings

    rows = load_catalog_rows(get_settings().catalog_csv)
    assert rows
    assert all(row["name"] and row["region"] for row in rows)
    kinds = {row["kind"] for row in rows}
    assert SourceKind.MEDIA in kinds
    municipalities = [row for row in rows if row["kind"] is SourceKind.MUNICIPALITY]
    assert municipalities
    assert all(str(row["name"]).startswith("Municipalidad de ") for row in municipalities)
