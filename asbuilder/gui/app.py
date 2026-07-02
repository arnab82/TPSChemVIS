"""
Entry point: `python -m asbuilder.gui.app [project_dir]`
              or `asbuilder` (after `pip install -e .`)

On first launch the setup wizard runs automatically to clone and build
TPSChem.jl.  Config is persisted at ~/.asbuilder/config.json so subsequent
launches need no flags.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Active Space Builder")
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=None,
        help="Project folder to open or create (default: ~/asbuilder_projects/untitled.qcproj)",
    )
    parser.add_argument("--julia-bin", default=None, help="Julia executable (default: julia)")
    parser.add_argument(
        "--julia-project",
        default=None,
        help="Override path to TPSChem.jl directory (saved to config on first use)",
    )
    parser.add_argument(
        "--vibemol-root",
        default=None,
        help="Path to vendored VibeMol static build",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Force the setup wizard even if TPSChem.jl is already configured",
    )
    args = parser.parse_args()

    from PyQt6.QtWidgets import QApplication
    import asbuilder.config as cfg
    from asbuilder.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Active Space Builder")
    app.setOrganizationName("asbuilder")

    # Show a dialog for unhandled exceptions instead of silently exiting
    _orig_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        import traceback
        from PyQt6.QtWidgets import QMessageBox
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        dlg = QMessageBox()
        dlg.setWindowTitle("Unexpected error")
        dlg.setText(f"<b>{exc_type.__name__}</b>: {exc_value}")
        dlg.setDetailedText(msg)
        dlg.setIcon(QMessageBox.Icon.Critical)
        dlg.exec()
        _orig_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _excepthook

    # --- resolve julia_bin ---
    julia_bin = args.julia_bin or cfg.julia_bin()

    # --- resolve julia_project ---
    julia_project: Path | None = None
    if args.julia_project:
        julia_project = Path(args.julia_project)
        cfg.set_value("julia_project", str(julia_project))
    else:
        julia_project = cfg.julia_project()

    # Auto-detect workspace sibling as a convenience (dev layout)
    if julia_project is None:
        sibling = Path(__file__).parent.parent.parent.parent / "TPSChem.jl"
        if (sibling / "Project.toml").exists():
            julia_project = sibling
            cfg.set_value("julia_project", str(julia_project))

    # --- show setup wizard if TPSChem.jl not found ---
    if julia_project is None or args.setup:
        from asbuilder.gui.screens.setup_screen import SetupDialog
        dlg = SetupDialog(julia_bin=julia_bin)
        if dlg.exec() and dlg.chosen_path:
            julia_project = dlg.chosen_path
        elif julia_project is None:
            # User closed without configuring — still open the app, CMF will warn
            pass

    # --- resolve project dir ---
    if args.project_dir:
        project_dir = Path(args.project_dir)
    else:
        default_root = Path.home() / "asbuilder_projects"
        default_root.mkdir(exist_ok=True)
        project_dir = default_root / "untitled.qcproj"

    window = MainWindow(
        project_root=project_dir,
        julia_bin=julia_bin,
        julia_project=julia_project,
        vibemol_root=args.vibemol_root,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
