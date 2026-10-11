"""Static checks that Tableau and Power BI still line up with the exported data.

Neither tool can run in CI, so these tests check their project files instead:
  * the export's columns are exactly what both tools read,
  * every field the Power BI report uses exists in the semantic model,
  * every column and measure a DAX formula references exists,
  * the PBIR report files are valid against Microsoft's published schemas
    (when PBIR_SCHEMAS_DIR points at a checkout of microsoft/json-schemas).
"""
import json
import os
import re
import unittest
import zipfile
from pathlib import Path

from tests.helpers import REPO_ROOT

EXPORT = REPO_ROOT / "data" / "customer_support_tickets.csv"
PBI = REPO_ROOT / "powerbi"
MODEL = PBI / "CustomerSupportAnalytics.SemanticModel" / "definition"
REPORT = PBI / "CustomerSupportAnalytics.Report"
TWBX = REPO_ROOT / "tableau" / "dashboard" / "Customer Support Analytics.twbx"


def export_columns():
    return EXPORT.read_text(encoding="utf-8").splitlines()[0].split(",")


def _name(token):
    token = token.strip()
    return token[1:-1].replace("''", "'") if token.startswith("'") else token


def parse_tmdl():
    """Return {table: {"columns": {...}, "measures": {name: dax}, "sort_by": [...], "source": str}}."""
    tables = {}
    for path in sorted((MODEL / "tables").glob("*.tmdl")):
        lines = path.read_text(encoding="utf-8").splitlines()
        table = None
        current = None
        for i, line in enumerate(lines):
            if m := re.match(r"^table (.+)$", line):
                table = _name(m.group(1))
                tables[table] = {"columns": set(), "measures": {}, "sort_by": [], "source": ""}
            elif m := re.match(r"^\tcolumn ('[^']*(?:''[^']*)*'|\S+)", line):
                current = ("column", _name(m.group(1)))
                tables[table]["columns"].add(current[1])
            elif m := re.match(r"^\tmeasure ('[^']*(?:''[^']*)*'|\S+) =(.*)$", line):
                name, dax = _name(m.group(1)), m.group(2).strip()
                if not dax:
                    body = []
                    for nxt in lines[i + 1:]:
                        if not nxt.startswith("\t\t\t"):
                            break
                        body.append(nxt.strip())
                    dax = "\n".join(body)
                tables[table]["measures"][name] = dax
            elif m := re.match(r"^\t\tsortByColumn: (.+)$", line):
                tables[table]["sort_by"].append((current[1], _name(m.group(1))))
            elif line.startswith("\tpartition "):
                tables[table]["source"] = "\n".join(lines[i:])
    return tables


def report_fields():
    """Yield (visual_file, kind, entity, property) for every field a visual uses."""
    def walk(node, path):
        if isinstance(node, dict):
            for kind in ("Column", "Measure"):
                ref = node.get(kind)
                if isinstance(ref, dict) and "Property" in ref:
                    entity = ref.get("Expression", {}).get("SourceRef", {}).get("Entity")
                    if entity:
                        yield path, kind, entity, ref["Property"]
            for v in node.values():
                yield from walk(v, path)
        elif isinstance(node, list):
            for v in node:
                yield from walk(v, path)

    for f in sorted(REPORT.glob("definition/pages/*/visuals/*/visual.json")):
        yield from walk(json.loads(f.read_text(encoding="utf-8")), f.relative_to(REPORT))


class ExportSchemaTests(unittest.TestCase):
    def test_tableau_reads_exactly_the_exported_columns(self):
        with zipfile.ZipFile(TWBX) as z:
            twb = next(n for n in z.namelist() if n.endswith(".twb"))
            text = z.read(twb).decode("utf-8")
        tableau_columns = set(re.findall(r"<remote-name>([^<]+)</remote-name>", text))
        self.assertEqual(tableau_columns, set(export_columns()))

    def test_power_bi_reads_exactly_the_exported_columns(self):
        source = parse_tmdl()["Tickets"]["source"]
        typed = set(re.findall(r'\{"(\w+)", (?:type \w+|Int64\.Type)\}', source))
        removed = set(re.findall(r'"(\w+)"', re.search(r"Table\.RemoveColumns\([^{]*\{([^}]*)\}", source).group(1)))
        self.assertEqual(typed | removed, set(export_columns()))
        self.assertIn(f"Columns = {len(export_columns())}", source)


class PowerBiModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = parse_tmdl()

    def has(self, kind, entity, prop):
        t = self.tables.get(entity)
        if t is None:
            return False
        return prop in (t["columns"] if kind == "Column" else t["measures"])

    def test_report_fields_exist_in_model(self):
        fields = list(report_fields())
        self.assertGreater(len(fields), 30)
        for path, kind, entity, prop in fields:
            with self.subTest(visual=str(path), field=f"{entity}.{prop}"):
                self.assertTrue(self.has(kind, entity, prop), f"{kind} {entity}[{prop}] not in model")

    def test_dax_references_resolve(self):
        measures = {m for t in self.tables.values() for m in t["measures"]}
        for table, t in self.tables.items():
            for name, dax in t["measures"].items():
                with self.subTest(measure=name):
                    for tbl, col in re.findall(r"('[^']+'|\w+)\[([^\]]+)\]", dax):
                        self.assertIn(col, self.tables[_name(tbl)]["columns"], f"{name}: {tbl}[{col}]")
                    for ref in re.findall(r"(?<![\w'\]])\[([^\]]+)\]", dax):
                        self.assertIn(ref, measures, f"{name}: [{ref}]")

    def test_sort_by_columns_exist(self):
        for table, t in self.tables.items():
            for col, target in t["sort_by"]:
                self.assertIn(target, t["columns"], f"{table}[{col}] sorts by missing {target}")

    def test_relationships_point_at_real_columns(self):
        text = (MODEL / "relationships.tmdl").read_text(encoding="utf-8")
        refs = re.findall(r"(?:fromColumn|toColumn): (\w+)\.('[^']+'|\w+)", text)
        self.assertTrue(refs)
        for table, col in refs:
            self.assertIn(_name(col), self.tables[table]["columns"])

    def test_metrics_shared_with_warehouse_exist_in_model(self):
        """KPIs defined in the warehouse also exist as Power BI measures."""
        expected = {"Tickets", "Avg First Response (min)", "Avg Resolution (h)", "Response SLA %",
                    "Resolution SLA %", "CSAT", "Resolution Rate %", "Escalation Rate %",
                    "Escalated Share of Resolution Hours", "Agent Performance Score",
                    "Tickets (7-day avg)", "Tickets MoM %"}
        self.assertLessEqual(expected, set(self.tables["Tickets"]["measures"]))


@unittest.skipUnless(os.environ.get("PBIR_SCHEMAS_DIR"), "set PBIR_SCHEMAS_DIR to a microsoft/json-schemas checkout")
class PbirSchemaTests(unittest.TestCase):
    PREFIX = "https://developer.microsoft.com/json-schemas/"

    def test_report_files_match_published_schemas(self):
        from jsonschema import Draft7Validator
        from referencing import Registry, Resource

        root = Path(os.environ["PBIR_SCHEMAS_DIR"])

        def retrieve(uri):
            return Resource.from_contents(json.loads((root / uri[len(self.PREFIX):]).read_text()))

        registry = Registry(retrieve=retrieve)
        files = [p for p in PBI.rglob("*") if p.is_file() and "StaticResources" not in p.parts
                 and (p.suffix in {".json", ".pbir", ".pbism", ".pbip"} or p.name == ".platform")]
        checked = 0
        for f in files:
            doc = json.loads(f.read_text(encoding="utf-8"))
            schema_id = doc.get("$schema")
            if not schema_id:
                continue
            schema = json.loads((root / schema_id[len(self.PREFIX):]).read_text())
            errors = list(Draft7Validator(schema, registry=registry).iter_errors(doc))
            self.assertEqual(errors, [], f"{f.relative_to(PBI)}: {errors[:1]}")
            checked += 1
        self.assertGreater(checked, 30)


if __name__ == "__main__":
    unittest.main()
