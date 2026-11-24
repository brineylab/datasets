#!/usr/bin/env python3
"""Recheck downloaded parquet tables against the pinned EPAM archive.

Run `python verify_source.py <published dataset directory> <pcps.tar.gz>` after
cloning the repository recipe and downloading only pcps.tar.gz. The source card's
snippet shows the same DuckDB reads without this repository helper.
"""
import hashlib
import json
import sys
import tarfile
from pathlib import Path

import duckdb
import polars as pl


def read_csv(db, data, columns, types):
    """A typed, in-memory source read; all other columns are text."""
    # Declare all 20 physical CSV fields, including the generated integer row index.
    declarations = "'column0': 'BIGINT', " + ", ".join(
        repr(c) + ": " + repr(types.get(c, "VARCHAR")) for c in columns)
    selected = ", ".join('"' + c + '"' for c in columns)
    return db.sql(f"SELECT {selected} FROM read_csv(?::BLOB, header = true, all_varchar = true, "
                  f"columns = {{{declarations}}})", params=(data,))


def main():
    out, archive = Path(sys.argv[1]), Path(sys.argv[2])
    provenance = json.loads(pl.read_parquet(out / "provenance.parquet")["provenance_json"][0])
    types = provenance["conversion"]["duckdb_csv_reader"]["types"]
    columns = provenance["conversion"]["columns"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == provenance["source"]["sha256"]
    with tarfile.open(archive, "r:gz") as tar:
        members = {member.name: member for member in tar.getmembers()}
        for corpus, source in provenance["corpora"].items():
            data = tar.extractfile(members[source["source_member"]]).read()
            assert hashlib.sha256(data).hexdigest() == source["source_sha256"], f"{corpus}: source CSV sha256 differs"
            with duckdb.connect() as db:
                expected = read_csv(db, data, columns, types).fetch_arrow_table().combine_chunks()
                actual = db.read_parquet(str(out / corpus / "pcps.parquet")).fetch_arrow_table().combine_chunks()
            assert actual.num_rows == source["source_rows"]
            assert actual.schema == expected.schema and actual.equals(expected), f"{corpus}: a source value or row differs"
            print(f"{corpus}: source sha256 {source['source_sha256']}; all {source['source_rows']} ordered rows and values match")
    print("ok: all six parquets reproduce the pinned deposit tables")


if __name__ == "__main__":
    main()
