from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from asbuilder.io.chk_to_molden import normalize_molden_for_viewers


class MoldenGenerationTests(unittest.TestCase):
    def test_normalize_molden_for_viewers_uppercases_spherical_tags(self) -> None:
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "orbitals.molden"
            path.write_text(
                "\n".join(
                    [
                        "[Molden Format]",
                        "[Atoms] (AU)",
                        "[GTO]",
                        "[5d]",
                        "[7f]",
                        "[9g]",
                        "[MO]",
                        " Sym= A",
                        " Ene= 0.0",
                        " Spin= Alpha",
                        " Occup= 1.0",
                        "  1 0.1",
                    ]
                )
            )

            returned = normalize_molden_for_viewers(path)

            self.assertEqual(returned, path)
            text = path.read_text()
            self.assertNotIn("[5d]", text)
            self.assertNotIn("[7f]", text)
            self.assertNotIn("[9g]", text)
            self.assertIn("[5D]", text)
            self.assertIn("[7F]", text)
            self.assertIn("[9G]", text)
            self.assertIn("[MO]", text)


if __name__ == "__main__":
    unittest.main()
