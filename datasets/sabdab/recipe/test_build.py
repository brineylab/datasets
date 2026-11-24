"""Small offline regression fixture for the source join, publication checks and CIF round trip."""
import csv
import gzip
import io
import json
import runpy
import tarfile
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
build = runpy.run_path(str(HERE / "build"))

verify = runpy.run_path(str(HERE / "test"))["verify"]


class Export:
    base = "fixture"
    case = ""
    state_reads = 0

    def __init__(self):
        self.rows = []
        self.objects = {}
        self.files = {}
        self.archive_names = {}
        for i, (h, l, antigens) in enumerate([("H", "L", ["C", "D"]), ("h", "l", ["C", "D"]), (None, "E", [])]):
            pdb = "pdb_0000test"
            key = "-".join(c for c in (pdb, h, l) if c)
            ab = f"pair{i}"
            self.rows.append({"INSTANCE": key, "PDB": pdb, "SABDAB_ID": ab, "HEAVY_ID": h,
                              "LIGHT_ID": l, "Hchain": h, "Lchain": l, "CDR-H3": "A"*16 if h else None,
                              "antigen_chain": "|".join(antigens), "date": "2026/11/24",
                              "heavy_taxid": 9606 if h else None, "extra_summary_column": "kept"})
            name = f"{pdb}_{h or '+'}_{l}_{'abag' if antigens else 'ab'}{i + 1 if i < 2 else ''}.cif.gz"
            self.archive_names[key] = name
            chains = " ".join(c for c in (h, l, *antigens) if c)
            self.files[name] = ("data_test\r\n_entry.id TEST\r\nloop_\r\n_atom_site.auth_asym_id\r\n"
                                "_atom_site.label_seq_id\r\n" + "\r\n".join(
                                    f"{chain} 1" for chain in (h, l, *antigens) if chain) + "\r\n").encode()

    def get(self, path):
        if path == "/stats/summary":
            self.state_reads += 1
            marker = "new" if self.case == "refresh" and self.state_reads > 1 else "initial"
            return json.dumps(dict(last_update=marker, antibody_instances=3)).encode()
        if path == "/download/all-summary":
            buf = io.StringIO()
            csvfile = csv.DictWriter(buf, self.rows[0])
            csvfile.writeheader()
            csvfile.writerows(self.rows)
            if self.case == "duplicate":
                csvfile.writerow(self.rows[0])
            return buf.getvalue().encode("utf-8-sig")
        if path.startswith("/pdb?"):
            return json.dumps({"total": 1, "results": [self.objects["/pdb/pdb_0000test"]]}).encode()
        if path.startswith("/pdb/"):
            raise AssertionError("bulk list already supplied the full PDB record")
        return json.dumps(self.objects[path]).encode()

    def archive(self, path):
        with tarfile.open(path, "w") as tar:
            def add(name, data):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            buf = io.StringIO()
            fields = [*self.rows[0], "filename_in_archive"]
            csvfile = csv.DictWriter(buf, fields)
            csvfile.writeheader()
            csvfile.writerows([{**row, "filename_in_archive": "instance_structures/" + self.archive_names[row["INSTANCE"]]}
                               for row in self.rows])
            add("SAbDab_summary.csv", buf.getvalue().encode())
            for i, (name, data) in enumerate(self.files.items()):
                if self.case == "missing" and i == 0:
                    continue
                if self.case == "ambiguous" and i == 2:
                    # A superset alone would match both H/L and h/l; exact chain equality must not decide it.
                    name = "instance_structures/ambiguous.cif.gz"
                if self.case == "unbound_ab":
                    # Source examples use _ab even where the summary names antigen chains.
                    name = name.replace("_abag", "_ab")
                add("instance_structures/" + name, gzip.compress(data))


class SnapshotTest(unittest.TestCase):
    maxDiff = None

    def capture(self, root, source):
        data = root / "data"
        data.mkdir()
        build["assemble"](source, {"last_update": "initial"}, root, data)

    def test_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = Export()
            self.capture(root, source)
            verify(root)
            rows = pq.read_table(root / "data").to_pylist()
            self.assertEqual([r["PDB_ID"] for r in rows], [rows[0]["PDB"]]*3)
            self.assertEqual([r["cdrh3_length_aa"] for r in rows], [16, 16, None])
            self.assertEqual([r["extra_summary_column"] for r in rows], ["kept"]*3)
            self.assertEqual([r["archive_filename"] for r in rows], ["instance_structures/" + name for name in source.files])
            self.assertEqual([r["cif"].encode() for r in rows], list(source.files.values()))
            with self.assertRaisesRegex(ValueError, "pinned last_update"):
                verify(root, {"last_update": "another release", "summary_sha256": ""})

    def test_unbound_export_filename_does_not_identify_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = Export()
            source.case = "unbound_ab"
            self.capture(root, source)
            rows = pq.read_table(root / "data").to_pylist()
            self.assertTrue(all("_ab" in row["archive_filename"] and "_abag" not in row["archive_filename"] for row in rows))

    def test_inconsistent_exports(self):
        for case, message in [("duplicate", "duplicate source identifier"),
                              ("missing", "Missing archive"), ("ambiguous", "exactly one instance"),
                              ("refresh", "Source changed")]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                source = Export()
                source.case = case
                with self.assertRaisesRegex(ValueError, message):
                    self.capture(Path(tmp), source)


if __name__ == "__main__":
    unittest.main()
