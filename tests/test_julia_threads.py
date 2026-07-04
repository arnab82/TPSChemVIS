import unittest

from asbuilder.julia_bridge.runner import julia_thread_args, render_driver


class JuliaThreadTests(unittest.TestCase):
    def test_julia_thread_args_accepts_auto_and_positive_integers(self) -> None:
        self.assertEqual(julia_thread_args(None), [])
        self.assertEqual(julia_thread_args(""), [])
        self.assertEqual(julia_thread_args("auto"), ["--threads=auto"])
        self.assertEqual(julia_thread_args("4"), ["--threads=4"])
        self.assertEqual(julia_thread_args(2), ["--threads=2"])

    def test_julia_thread_args_rejects_invalid_values(self) -> None:
        for value in ("0", "-2", "many"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    julia_thread_args(value)

    def test_tpsci_and_spt_drivers_log_julia_threads(self) -> None:
        base_context = {
            "cmf_result_path": "/tmp/cmf_result.jld2",
            "output_dir": "/tmp/export",
        }

        tpsci = render_driver(
            "driver_tpsci.jl.j2",
            {
                **base_context,
                "spin_adapt": False,
                "add_spin_fock": False,
                "compute_s2": False,
            },
        )
        spt = render_driver("driver_spt.jl.j2", {**base_context, "compute_s2": False})

        self.assertIn("Base.Threads.nthreads()", tpsci)
        self.assertIn("Base.Threads.nthreads()", spt)


if __name__ == "__main__":
    unittest.main()
