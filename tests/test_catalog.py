import shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from helpers import ROOT
import check  # noqa: E402
import catalog  # noqa: E402


class CatalogTests(unittest.TestCase):
    def test_format_count_and_bytes_handle_scales_and_rounding_boundaries(self):
        self.assertEqual(catalog.format_count(300, "pairs"), "300 pairs")
        self.assertEqual(catalog.format_count(22866, "structures"), "22.9k structures")
        self.assertEqual(catalog.format_count(542378, "structures"), "542k structures")
        self.assertEqual(catalog.format_count(1186496, "pairs"), "1.19M pairs")
        self.assertEqual(catalog.format_count(299748717, "sequences"), "300M sequences")
        self.assertEqual(catalog.format_count(999950, "rows"), "1.00M rows")
        self.assertEqual(catalog.format_bytes(0), "0 B")
        self.assertEqual(catalog.format_bytes(999), "999 B")
        self.assertEqual(catalog.format_bytes(48252), "48.3 KB")
        self.assertEqual(catalog.format_bytes(999950), "1.00 MB")
        self.assertEqual(catalog.format_bytes(1518620607), "1.52 GB")
        self.assertEqual(catalog.format_bytes(120558318035), "121 GB")

    def test_escape_cell_collapses_newlines_and_escapes_pipes(self):
        self.assertEqual(catalog.escape_cell("a | b\n  c\t|d"), r"a \| b c \|d")

    def test_render_catalog_filters_unpublished_uses_hub_org_and_handles_missing_optional_fields(self):
        tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, tmp)
        (tmp / "hub.toml").write_text('org = "exampleorg"\ntoolshed = "ghcr.io/exampleorg/toolshed"\n')
        (tmp / "datasets").mkdir(); (tmp / "datasets" / ".DS_Store").write_text("junk")

        def add_ds(name, version, desc, extra="", rec_version=None, rec_exit=0, files=()):
            d = tmp / "datasets" / name; d.mkdir(parents=True)
            (d / "SKILL.md").write_text(
                f'---\nname: {name}\ndescription: "{desc}"\nmetadata:\n  version: {version}\n  tools: datascience@1.2.0\n  license: mit\n{extra}---\n'
            )
            if rec_version is not None:
                r = tmp / "results" / name; r.mkdir(parents=True)
                manifest = "".join(f"file {p} {sz} {'0' * 64}\n" for p, sz in files)
                (r / f"{rec_version}.txt").write_text(
                    f"---\ndataset: {name}\nversion: {rec_version}\nexit: {rec_exit}\n---\n{manifest}"
                )

        add_ds("beta", "1.0.0", "No count or files.", rec_version="1.0.0")
        add_ds("alpha", "1.2.0", "A | B   extra spaces.", "  count: 1500\n  unit: pairs\n", rec_version="1.2.0", files=[("a.parquet", 2048)])
        add_ds("gamma", "1.0.0", "Failed build.", rec_version="1.0.0", rec_exit=1)
        add_ds("delta", "1.0.0", "Missing record.")
        add_ds("epsilon", "2.0.0", "Only old record.", rec_version="1.0.0")
        out = catalog.render_catalog(tmp)
        self.assertIn("2 published datasets.", out)
        self.assertIn('`snapshot_download("exampleorg/<name>", repo_type="dataset", revision="v<version>")`', out)
        rows = [line for line in out.splitlines() if line.startswith("| [")]
        self.assertEqual(rows, [
            r"| [alpha](datasets/alpha/SKILL.md) | [v1.2.0](https://huggingface.co/datasets/exampleorg/alpha/tree/v1.2.0) | 1.50k pairs | 2.05 KB | mit | datascience@1.2.0 | A \| B extra spaces. |",
            "| [beta](datasets/beta/SKILL.md) | [v1.0.0](https://huggingface.co/datasets/exampleorg/beta/tree/v1.0.0) | — | — | mit | datascience@1.2.0 | No count or files. |",
        ])

    def test_cli_stdout_and_write_flag(self):
        tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, tmp)
        (tmp / "hub.toml").write_text('org = "exampleorg"\ntoolshed = "ghcr.io/exampleorg/toolshed"\n')
        (tmp / "datasets" / "one").mkdir(parents=True)
        (tmp / "datasets" / "one" / "SKILL.md").write_text(
            '---\nname: one\ndescription: "One dataset."\nmetadata:\n  version: 1.0.0\n  tools: datascience@1.0.0\n  license: mit\n---\n'
        )
        (tmp / "results" / "one").mkdir(parents=True)
        (tmp / "results" / "one" / "1.0.0.txt").write_text("---\ndataset: one\nversion: 1.0.0\nexit: 0\n---\n")
        r1 = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "catalog.py"), "--root", str(tmp)], capture_output=True, text=True, check=True)
        self.assertEqual(r1.stdout, catalog.render_catalog(tmp))
        self.assertIn("1 published dataset.", r1.stdout)
        subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "catalog.py"), "--root", str(tmp), "--write"], check=True)
        self.assertEqual((tmp / "CATALOG.md").read_text(encoding="utf-8"), r1.stdout)

    def test_live_repo_renders_every_published_dataset(self):
        out = catalog.render_catalog(ROOT)
        expected = [
            d.name for d in sorted((ROOT / "datasets").iterdir())
            if d.is_dir() and (d / "SKILL.md").is_file()
            and (rec := ROOT / "results" / d.name / f"{check.frontmatter(d / 'SKILL.md')['metadata']['version']}.txt").is_file()
            and check.parse_record(rec)["exit"] == 0
        ]
        rows = [line for line in out.splitlines() if line.startswith("| [")]
        self.assertEqual(len(rows), len(expected))
        for name, row in zip(expected, rows):
            self.assertIn(f"[{name}](datasets/{name}/SKILL.md)", row)
            self.assertEqual(row.replace(r"\|", "").count("|"), 8)  # 7 columns


if __name__ == "__main__":
    unittest.main()
