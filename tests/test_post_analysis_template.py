import unittest

from asbuilder.julia_bridge.runner import render_driver


class PostAnalysisTemplateTests(unittest.TestCase):
    def test_wavefunction_post_analysis_supports_spt_results(self) -> None:
        script = render_driver(
            "driver_wavefunction_post_analysis.jl.j2",
            {
                "cmf_result_path": "/tmp/cmf_result.jld2",
                "wavefunction_result_path": "/tmp/spt_result.jld2",
                "output_dir": "/tmp/post_analysis",
                "wavefunction_key": "auto",
                "nroots": 4,
                "ct_thresh": "1e-5",
            },
        )

        self.assertIn('"v_var"', script)
        self.assertIn("TPSChem.SPTstate", script)
        self.assertIn("function sector_weight_spt", script)
        self.assertIn("tucker.core[root]", script)
        self.assertNotIn("TPSChem.general_ct_analysis", script)
        self.assertNotIn("TPSChem.general_ct_table", script)


if __name__ == "__main__":
    unittest.main()
