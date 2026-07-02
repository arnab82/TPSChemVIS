"""
Screen 7: choose TPSCI, SPT, or post-processing methods (PT2/CEPA/FCI),
render the Julia driver from Jinja2 templates, preview it, run it locally,
or package everything for HPC submission.

Local run and HPC package are independent: you can run TPSCI locally to
check results, then package for a larger HPC job with tighter thresholds.
"""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


from asbuilder.gui.widgets.collapsible_section import CollapsibleSection as _CollapsibleSection
from asbuilder.gui.widgets.log_pane import LogPane
from asbuilder.julia_bridge.runner import PINNED_JULIA_VERSION, write_driver


class ExportScreen(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cmf_result_path: Path | None = None
        self._export_dir: Path | None = None
        self._julia_project: Path | None = None
        self._worker = None

        # --- method selector ---
        self._method = QComboBox()
        self._method.addItems(["TPSCI", "SPT", "PT2", "CEPA", "FCI-solve"])
        self._method.currentTextChanged.connect(self._on_render)

        # --- shared thresholds ---
        self._thresh_var = QLineEdit("1e-2")
        self._thresh_foi = QLineEdit("1e-3")
        self._thresh_pt = QLineEdit("1e-3")
        self._max_roots = QSpinBox()
        self._max_roots.setRange(1, 200)
        self._max_roots.setValue(20)
        self._nroots = QSpinBox()
        self._nroots.setRange(1, 50)
        self._nroots.setValue(1)

        thresh_form = QFormLayout()
        thresh_form.addRow("Method", self._method)
        thresh_form.addRow("thresh_var (TPSCI/SPT)", self._thresh_var)
        thresh_form.addRow("thresh_foi", self._thresh_foi)
        thresh_form.addRow("thresh_pt / PT2", self._thresh_pt)
        thresh_form.addRow("max_roots (eigenbasis)", self._max_roots)
        thresh_form.addRow("nroots", self._nroots)

        calc_group = _CollapsibleSection("Calculation settings")
        calc_inner = QVBoxLayout()
        calc_inner.addLayout(thresh_form)
        calc_group.set_body_layout(calc_inner)

        # --- HPC export ---
        self._job_name = QLineEdit("tpsci_job")
        self._account = QLineEdit()
        self._partition = QLineEdit("normal")
        self._nodes = QSpinBox()
        self._nodes.setRange(1, 1000)
        self._nodes.setValue(1)
        self._walltime = QLineEdit("24:00:00")

        hpc_form = QFormLayout()
        hpc_form.addRow("Job name", self._job_name)
        hpc_form.addRow("Account", self._account)
        hpc_form.addRow("Partition", self._partition)
        hpc_form.addRow("Nodes", self._nodes)
        hpc_form.addRow("Walltime", self._walltime)

        hpc_group = _CollapsibleSection("HPC submission (SLURM)")
        hpc_group.set_body_layout(hpc_form)

        # --- script previews (collapsed into a small collapsible tab at bottom) ---
        from PyQt6.QtWidgets import QPlainTextEdit, QSplitter
        self._driver_preview = QPlainTextEdit()
        self._driver_preview.setReadOnly(True)
        self._slurm_preview = QPlainTextEdit()
        self._slurm_preview.setReadOnly(True)
        for w in (self._driver_preview, self._slurm_preview):
            f = w.font()
            f.setFamily("monospace")
            w.setFont(f)

        self._preview_tabs = QTabWidget()
        self._preview_tabs.addTab(self._driver_preview, "driver_*.jl")
        self._preview_tabs.addTab(self._slurm_preview, "submit.slurm")

        # --- log pane — gets the bulk of the space ---
        self._log = LogPane()

        # --- buttons ---
        render_btn = QPushButton("Render script")
        render_btn.clicked.connect(self._on_render)
        self._run_local_btn = QPushButton("▶  Run locally")
        self._run_local_btn.clicked.connect(self._on_run_local)
        package_btn = QPushButton("Package for HPC...")
        package_btn.clicked.connect(self._on_package)

        btn_row = QHBoxLayout()
        btn_row.addWidget(render_btn)
        btn_row.addWidget(self._run_local_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(package_btn)

        self._status = QLabel(f"Target: Julia {PINNED_JULIA_VERSION}")

        # calc_group and hpc_group are direct splitter children so collapsing them
        # forces the splitter to reclaim space and give it to log/preview.
        from PyQt6.QtCore import Qt as _Qt
        splitter = QSplitter(_Qt.Orientation.Vertical)
        splitter.setHandleWidth(8)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(calc_group)
        splitter.addWidget(hpc_group)
        splitter.addWidget(self._log)
        splitter.addWidget(self._preview_tabs)
        splitter.setStretchFactor(0, 0)   # calc section — fixed when collapsed
        splitter.setStretchFactor(1, 0)   # hpc section — fixed when collapsed
        splitter.setStretchFactor(2, 4)   # log gets extra space
        splitter.setStretchFactor(3, 1)   # preview

        layout = QVBoxLayout(self)
        layout.addWidget(splitter, stretch=1)
        layout.addLayout(btn_row)
        layout.addWidget(self._status)
        self.setLayout(layout)

    def set_inputs(self, cmf_result_path: str | Path, export_dir: str | Path,
                   julia_project: str | Path | None = None) -> None:
        self._cmf_result_path = Path(cmf_result_path)
        self._export_dir = Path(export_dir)
        self._julia_project = Path(julia_project) if julia_project else None
        self._export_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------

    def _build_context(self) -> tuple[str, dict]:
        method = self._method.currentText()
        ctx = dict(
            cmf_result_path=str(self._cmf_result_path),
            output_dir=str(self._export_dir),
            max_roots=self._max_roots.value(),
            nroots=self._nroots.value(),
            thresh_var=self._thresh_var.text(),
            thresh_foi=self._thresh_foi.text(),
            thresh_pt=self._thresh_pt.text(),
        )
        template_map = {
            "TPSCI": "driver_tpsci.jl.j2",
            "SPT": "driver_spt.jl.j2",
            "PT2": "driver_pt2.jl.j2",
            "CEPA": "driver_cepa.jl.j2",
            "FCI-solve": "driver_fci_solve.jl.j2",
        }
        return template_map.get(method, "driver_tpsci.jl.j2"), ctx

    def _driver_name(self) -> str:
        method = self._method.currentText().lower().replace("-", "_").replace(" ", "_")
        return f"driver_{method}.jl"

    def _on_render(self) -> None:
        if self._cmf_result_path is None or self._export_dir is None:
            self._status.setText("No CMF result set -- finish the CMF step first.")
            return
        try:
            from asbuilder.julia_bridge.runner import render_driver

            template, ctx = self._build_context()
            driver_text = render_driver(template, ctx)
            self._driver_preview.setPlainText(driver_text)

            slurm_ctx = dict(
                job_name=self._job_name.text(),
                account=self._account.text(),
                partition=self._partition.text(),
                nodes=self._nodes.value(),
                walltime=self._walltime.text(),
                driver_script=f"export/{self._driver_name()}",
                julia_project=".",
                use_juliaup=False,
            )
            slurm_text = render_driver("submit.slurm.j2", slurm_ctx)
            self._slurm_preview.setPlainText(slurm_text)
            self._status.setText(f"Rendered {template} (Julia {PINNED_JULIA_VERSION}).")
        except Exception as exc:
            self._status.setText(f"Render failed: {exc}")

    def _on_run_local(self) -> None:
        if self._cmf_result_path is None or self._export_dir is None:
            self._log.append_line("[export] no CMF result -- finish CMF step first.")
            return
        if self._worker is not None and self._worker.state() != 0:
            self._log.append_line("[export] a job is already running.")
            return

        template, ctx = self._build_context()
        driver_path = write_driver(template, ctx, self._export_dir / self._driver_name())
        self._log.append_line(f"[export] wrote {driver_path}, launching Julia...")
        self._run_local_btn.setEnabled(False)

        from asbuilder.gui.workers import JuliaProcessWorker

        julia_project = self._julia_project or self._cmf_result_path.parent.parent
        log_path = self._export_dir / "export.log"
        self._worker = JuliaProcessWorker(
            driver_path, julia_project,
            parent=self, log_path=log_path,
        )
        self._worker.line_received.connect(self._log.append_line)
        self._worker.finished_ok.connect(self._on_run_finished)
        self._worker.failed.connect(self._on_run_failed)
        self._worker.start()

    def _on_run_finished(self, exit_code: int) -> None:
        self._run_local_btn.setEnabled(True)
        if exit_code == 0:
            self._log.append_line("[export] Julia finished OK.")
        else:
            self._log.append_line(f"[export] Julia exited with code {exit_code}.")

    def _on_run_failed(self, message: str) -> None:
        self._run_local_btn.setEnabled(True)
        self._log.append_line(f"[export] FAILED: {message}")

    def _on_package(self) -> None:
        if self._export_dir is None or self._cmf_result_path is None:
            self._status.setText("Nothing to package yet -- render first.")
            return
        if not self._driver_preview.toPlainText():
            self._on_render()

        template, ctx = self._build_context()
        driver_path = write_driver(template, ctx, self._export_dir / self._driver_name())

        slurm_ctx = dict(
            job_name=self._job_name.text(),
            account=self._account.text(),
            partition=self._partition.text(),
            nodes=self._nodes.value(),
            walltime=self._walltime.text(),
            driver_script=f"export/{self._driver_name()}",
            julia_project=".",
            use_juliaup=False,
        )
        write_driver("submit.slurm.j2", slurm_ctx, self._export_dir / "submit.slurm")

        if self._cmf_result_path.exists():
            shutil.copy2(self._cmf_result_path, self._export_dir / self._cmf_result_path.name)

        zip_path, _ = QFileDialog.getSaveFileName(
            self, "Save export package",
            f"{self._method.currentText().lower()}_export.zip",
            "Zip files (*.zip)",
        )
        if not zip_path:
            return
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in self._export_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=path.relative_to(self._export_dir.parent))
        self._status.setText(f"Packaged -> {zip_path}")
