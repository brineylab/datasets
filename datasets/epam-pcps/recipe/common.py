"""Definitions and the canonical family subsample for EPAM PCP corpora."""
import hashlib

COLUMNS = [
    "sample_id", "family", "parent_name", "parent", "child_name", "child",
    "branch_length", "depth", "distance", "v_gene", "j_gene",
    "cdr1_codon_start", "cdr1_codon_end", "cdr2_codon_start", "cdr2_codon_end",
    "cdr3_codon_start", "cdr3_codon_end", "parent_is_naive", "child_is_leaf",
]
NUMERIC = {
    "branch_length": "DOUBLE", "depth": "BIGINT", "distance": "DOUBLE",
    "cdr1_codon_start": "BIGINT", "cdr1_codon_end": "BIGINT",
    "cdr2_codon_start": "BIGINT", "cdr2_codon_end": "BIGINT",
    "cdr3_codon_start": "BIGINT", "cdr3_codon_end": "BIGINT",
    "parent_is_naive": "BOOLEAN", "child_is_leaf": "BOOLEAN",
}
CORPORA = {
    "flairr": (
        "pcp_inputs/ford-flairr-seq-prod_pcp_2024-07-26_MASKED_NI_noN_no-naive.csv",
        2798, "3ee40a2db0f943d665e3ff0aebcbf18986e1259c6cfd89708bd8019d7d30a815"),
    "race": (
        "pcp_inputs/rodriguez-airr-seq-race-prod_pcp_2024-07-28_MASKED_NI_noN_no-naive.csv",
        20656, "e92f20a68d88538839fa1dd89981bfec3bc3c2b50cb6ce888f24f66c48bce675"),
    "tang": (
        "pcp_inputs/tang-deepshm-prod_pcp_2024-08-08_MASKED_NI_noN_no-naive.csv",
        505915, "b91b41b71ba7e91dc0075f7564b3f37e098853fc2eebb62af5800d5936a0a9c7"),
    "wyatt": (
        "pcp_inputs/wyatt-10x-1p5m_paired-igh_fs-all_pcp_2024-11-22_NI_noN_no-naive.csv",
        193601, "753c751f6601d5eb3988c9967edc570a58eb84ea8def51b1ee7e70c007107d0f"),
    "replay_igh": (
        "pcp_gcreplay_inputs/igh/gctrees_2025-01-10-full_igh_pcp_NoBackMuts.csv",
        10056, "acef28498c0b8d8f1f448dd3f327b6952d04fca008367ab1a1f51d87fd1a7de1"),
    "replay_igk": (
        "pcp_gcreplay_inputs/igk/gctrees_2025-01-10-full_igk_pcp_NoBackMuts.csv",
        10054, "564183cad60695584444bb360bffc4ee8ec7870d5d7504bf4d30259133228845"),
}


def csv_source(db, path_or_blob):
    """Read the 19 PCP fields, excluding the deposit's unnamed pandas index column."""
    declared = ", ".join(repr(c) + ": " + repr(NUMERIC.get(c, "VARCHAR")) for c in COLUMNS)
    selected = ", ".join('"' + c + '"' for c in COLUMNS)
    if isinstance(path_or_blob, bytes):
        # With a BLOB, DuckDB names the leading empty-header column column0. Declare
        # that physical INTEGER field too, then select only the 19 published PCP fields.
        declared = "'column0': 'BIGINT', " + declared
        return db.sql(f"SELECT {selected} FROM read_csv(?::BLOB, header = true, all_varchar = true, "
                      f"columns = {{{declared}}})", params=(path_or_blob,))
    options = f"types = {{{', '.join(repr(c) + ': ' + repr(NUMERIC.get(c, 'VARCHAR')) for c in COLUMNS)}}}"
    return db.sql(f"SELECT {selected} FROM read_csv(?, header = true, {options})", params=(str(path_or_blob),))


def family_order_key(seed, sample_id, family):
    """The seeded family order: lowercase hex SHA-256 over the explicitly delimited pair."""
    assert isinstance(sample_id, str) and isinstance(family, str)
    key = f"{seed}:{len(sample_id)}:{sample_id}{len(family)}:{family}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def subsample(table, seed, target):
    """Accumulate whole `(sample_id, family)` groups in seeded-hash order until >= target.

    The crossing family is included whole; output rows retain corpus order.
    """
    import polars as pl

    counts = table.group_by("sample_id", "family", maintain_order=True).len()
    ordered = sorted(counts.iter_rows(named=True),
                     key=lambda r: family_order_key(seed, r["sample_id"], r["family"]))
    selected, total = [], 0
    for row in ordered:
        if total >= target:
            break
        selected.append(row)
        total += row["len"]
    if not selected or total < target:
        raise ValueError(f"subsample has {total} rows, under target {target}")
    chosen = {(row["sample_id"], row["family"]) for row in selected}
    mask = [key in chosen for key in zip(table["sample_id"].to_list(), table["family"].to_list())]
    result = table.filter(pl.Series(mask))
    if result.height != total or result.group_by("sample_id", "family").len().height != len(chosen):
        raise ValueError("subsample did not select every row of each chosen family exactly once")
    # An actual digest collision needs an explicit tie key, not implementation-dependent sort state.
    for previous, row in zip(selected, selected[1:]):
        key = family_order_key(seed, previous["sample_id"], previous["family"])
        assert key != family_order_key(seed, row["sample_id"], row["family"]), "family order needs a collision tie-break"
    return result, total, total - target, len(chosen)
