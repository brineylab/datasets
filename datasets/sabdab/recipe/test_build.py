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
        for i, (h, l, antigens) in enumerate([("A1", "A2", ["C", "D"]), (None, "E", [])]):
            pdb = "pdb_0000test"
            key = "-".join(c for c in (pdb, h, l) if c)
            ab = f"pair{i}"
            self.rows.append({"INSTANCE": key, "PDB": pdb, "SABDAB_ID": ab, "HEAVY_ID": h,
                              "LIGHT_ID": l, "Hchain": h, "Lchain": l, "CDR-H3": "A"*16 if h else None,
                              "antigen_chain": "|".join(antigens),
                              "heavy_taxid": 9606 if h else None, "extra_summary_column": "kept"})
            name = f"{pdb}_{h or '+'}_{l}_{'abag' if antigens else 'ab'}.cif.gz"
            chains = " ".join(c for c in (h, l, *antigens) if c)
            self.files[name] = ("data_test\r\n_entry.id TEST\r\nloop_\r\n_atom_site.auth_asym_id\r\n" + chains + "\r\n").encode()

    def get(self, path):
        if path == "/stats/summary":
            self.state_reads += 1
            marker = "new" if self.case == "refresh" and self.state_reads > 1 else "initial"
            return json.dumps(dict(last_update=marker, antibody_instances=2)).encode()
        if path == "/download/all-summary":
            buf = io.StringIO()
            csvfile = csv.DictWriter(buf, self.rows[0])
            csvfile.writeheader()
            csvfile.writerows(self.rows)
            if self.case == "duplicate":
                csvfile.writerow(self.rows[0])
            return buf.getvalue().encode()
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
            add("SAbDab_summary.csv", self.get("/download/all-summary"))
            for i, (name, data) in enumerate(self.files.items()):
                if self.case == "missing" and i == 0:
                    continue
                add("instance_structures/" + name, gzip.compress(data))


class SnapshotTest(unittest.TestCase):
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
            a, b = pq.read_table(root / "data").to_pylist()
            self.assertEqual([a["PDB_ID"], b["PDB_ID"]], [a["PDB"]]*2)
            self.assertEqual([a["cdrh3_length_aa"], b["cdrh3_length_aa"]], [16, None])
            self.assertEqual(a["extra_summary_column"], "kept")
            self.assertEqual(a["cif"].encode(), next(iter(source.files.values())))
            with self.assertRaisesRegex(ValueError, "pinned last_update"):
                verify(root, {"last_update": "another release", "summary_sha256": ""})

    def test_inconsistent_exports(self):
        for case, message in [("duplicate", "duplicate source identifier"),
                              ("missing", "Missing archive"), ("refresh", "Source changed")]:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                source = Export()
                source.case = case
                with self.assertRaisesRegex(ValueError, message):
                    self.capture(Path(tmp), source)


if __name__ == "__main__":
    unittest.main()
