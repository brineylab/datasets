"""Inspect 2vyr's source/export instance mapping and polymer-chain accounting."""
import csv
import gzip
import io
import json
import os
import tarfile
from collections import Counter
from pathlib import Path

from Bio.PDB.MMCIF2Dict import MMCIF2Dict

campaign = Path(os.environ["FLYLOFT_CAMPAIGN"])
archives = sorted(set(campaign.glob("datasets/sabdab/*/.work/*/instances.tar"))
                  | set(campaign.glob("diagnostics/**/instances.tar")),
                  key=lambda path: path.stat().st_mtime, reverse=True)
if not archives:
    raise RuntimeError("No downloaded SAbDab archive is cached in this campaign")
archive = archives[0]
rows = []
with tarfile.open(archive, "r|*") as tar:
    for member in tar:
        if member.isfile() and member.name.lower().endswith("sabdab_summary.csv"):
            data = tar.extractfile(member).read().decode("utf-8-sig")
            rows = [row for row in csv.DictReader(io.StringIO(data), strict=True)
                    if row["PDB"].lower() == "pdb_00002vyr"]
            break
print("ARCHIVE", archive)
print("SUMMARY", json.dumps(rows, indent=2))
wanted = {"instance_structures/" + row["filename_in_archive"].removeprefix("instance_structures/") for row in rows}
report = []
with tarfile.open(archive, "r|*") as tar:
    for member in tar:
        if member.name not in wanted:
            continue
        raw = gzip.decompress(tar.extractfile(member).read()).decode()
        cif = MMCIF2Dict(io.StringIO(raw))
        item = {"path": member.name, "keys": sorted(cif)}
        for name in ("_entry.id", "_entity.id", "_entity.type", "_entity.pdbx_description",
                     "_entity_poly.entity_id", "_entity_poly.pdbx_strand_id",
                     "_struct_asym.id", "_struct_asym.entity_id",
                     "_pdbx_entity_nonpoly.entity_id", "_pdbx_entity_nonpoly.name",
                     "_pdbx_poly_seq_scheme.asym_id", "_pdbx_poly_seq_scheme.pdb_strand_id",
                     "_atom_site.label_asym_id", "_atom_site.auth_asym_id",
                     "_atom_site.label_entity_id", "_atom_site.label_seq_id"):
            if name in cif:
                item[name] = (dict(Counter(cif[name])) if name.startswith("_atom_site")
                              else cif[name])
        report.append(item)
        print("CROP", json.dumps(item, indent=2))
out = Path(os.environ["FLYLOFT_OUT"])
out.mkdir(parents=True, exist_ok=True)
(out / "2vyr-crops.json").write_text(json.dumps({"archive": str(archive), "summary": rows, "crops": report}, indent=2))
