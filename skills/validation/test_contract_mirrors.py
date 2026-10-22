"""Compare responsibility-matrix table columns, not incidental owner mentions."""
from __future__ import annotations

import re
import unittest

import _catalog


def table(text, header):
    rows = []
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(header))
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip().strip("`") for cell in line.strip("|").split("|")])
    names = [row[0] for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("duplicate table row")
    return {row[0]: row for row in rows}


def with_cell(text, header, name, column, value):
    """``text`` with one cell of the row ``name`` set to ``value``, or that row removed when ``value`` is None.

    The row is found the way ``table`` finds it, so a reworded row still gets
    mutated, and a missing one fails here instead of leaving the text unchanged.
    """
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(header))
    for index in range(start + 2, len(lines)):
        line = lines[index]
        if not line.startswith("|"):
            break
        body = line.rstrip("\r\n")
        cells = body.strip("|").split("|")
        if cells[0].strip().strip("`") != name:
            continue
        if value is None:
            lines[index] = ""
        else:
            cells[column] = f" {value} "
            lines[index] = "|" + "|".join(cells) + "|" + line[len(body):]
        return "".join(lines)
    raise AssertionError(f"no row {name!r} under {header!r}")


class ResponsibilityMirrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (_catalog.SKILLS / "contracts" / "responsibility-matrix.md").read_text(encoding="utf-8")
        cls.pipelines = _catalog.load_spec("pipelines.yaml")["pipelines"]
        cls.gates = _catalog.load_spec("gates.yaml")["boundaries"]
        cls.team = _catalog.load_spec("team-manifest.yaml")

    def assert_mirrors(self, text):
        layers = table(text, "| Layer |")
        expected = {name.replace("-", " ").upper(): pipeline["owner"] for name, pipeline in self.pipelines.items()}
        expected.update(INTAKE=self.team["front_door"], MEMORY=self.team["session_memory"],
                        GATE="the boundary's gatekeeper")
        self.assertEqual(set(layers), set(expected) | {"SAFETY"})
        for layer, owner in expected.items():
            self.assertEqual(layers[layer][2], owner, layer)
        safety = set(re.findall(r"[a-z]+", layers["SAFETY"][2])) - {"or"}
        self.assertEqual(safety, set(self.team["safety"]))
        coverage = table(text, "| Boundary |")
        self.assertEqual(set(coverage), set(self.gates))
        for pipeline in self.pipelines.values():
            boundary = pipeline["boundary"]
            phase = [stage for stage in pipeline["stages"] if stage["step"] == "phase-gate"]
            self.assertLessEqual(len(phase), 1)
            self.assertEqual(coverage[boundary][1:], [phase[0]["owner"] if phase else "none",
                                                    self.team["cross_stage_gatekeeper"], "yes" if phase else "no"])

    def test_responsibility_layer_owners_and_gate_columns_match_manifests(self):
        self.assert_mirrors(self.text)

    def test_owner_in_other_column_does_not_mask_owner_drift(self):
        drifted = with_cell(self.text, "| Layer |", "RELEASE", 2, "invented")
        owner = self.pipelines["release"]["owner"]
        self.assertIn(owner, " ".join(table(drifted, "| Layer |")["RELEASE"]),
                      "the RELEASE row no longer names its owner outside the Owner column, so this case tests nothing")
        with self.assertRaises(AssertionError):
            self.assert_mirrors(drifted)

    def test_gate_columns_and_missing_rows_are_compared(self):
        for column, value in ((1, "none"), (2, "invented"), (3, "no"), (None, None)):
            with self.subTest(column=column, value=value):
                drifted = with_cell(self.text, "| Boundary |", "design-to-build", column, value)
                self.assertNotEqual(self.text, drifted)
                with self.assertRaises(AssertionError):
                    self.assert_mirrors(drifted)
