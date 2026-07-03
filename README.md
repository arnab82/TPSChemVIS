# TPSChemVIS

**TPSChemVIS** is a desktop GUI for [TPSChem.jl](https://github.com/arnab82/TPSChem.jl) — a Julia package implementing Tensor Product State (TPS) quantum chemistry methods including TPSCI, SPT, CMF, and PT2.

TPSChemVIS provides a point-and-click interface for the full TPS pipeline: building active spaces from PySCF checkpoints, running Cluster Mean-Field (CMF) orbital optimization, and launching TPSCI/SPT/PT2 calculations — without writing a single script.

---

## Features

| Step | What you do | What the app does |
| ---- | ----------- | ----------------- |
| **Load** | Pick a PySCF `.chk` checkpoint | Reads geometry, basis, MO coefficients |
| **Visualize** | Inspect canonical MOs in 3D | Renders isosurfaces via VibeMol or launches desktop Jmol |
| **Cluster** | Assign MOs or atoms to clusters | Manual MO assignment or SPADE atom-based partitioning |
| **Active Space** | Click "Build" | Runs SPADE SVD, writes `h0/h1/h2.npy` integrals, saves per-cluster `.molden` files |
| **Inspect** | Review cluster orbitals in 3D | Dropdown switches between all-active and per-cluster moldens; edit `n_α / n_β` if needed |
| **CMF** | Choose Newton / BFGS / DIIS | Streams Julia output live; saves `cmf_result.jld2` |
| **TPSCI / Export** | Set thresholds, click Run | Renders Julia driver from Jinja2 templates, runs locally or packages for HPC (SLURM) |
| **Post-Analysis** | Load a TPSCI wavefunction | Runs TPSChem CT analysis and visualizes CT arrows, root totals, and sector weights |

**Additional capabilities:**

- **Resume anywhere** — Jump straight to CMF from saved integrals, or to TPSCI/Export from a saved CMF result, without restarting from scratch.
- **Persistent config** — TPSChem.jl path is saved to `~/.asbuilder/config.json` after first setup.
- **First-launch bootstrap** — Downloads VibeMol, clones and builds TPSChem.jl, and configures PyCall automatically.
- **Viewer choice** — Use embedded VibeMol or install desktop Jmol on demand from the viewer panel.
- **Navigation toolbar** — Click any pipeline step in the toolbar to jump back to it.
- **Collapsible panels** — Settings sections collapse to a header so the log output gets more screen space.

---

## Requirements

| Dependency | Version | Notes |
| ---------- | ------- | ----- |
| Python | ≥ 3.11 | |
| PyQt6 | ≥ 6.6 | GUI framework |
| PyQt6-WebEngine | ≥ 6.6 | Embedded VibeMol orbital viewer |
| Java | current JRE | Required only for desktop Jmol |
| PySCF | ≥ 2.4 | SCF + integral generation |
| NumPy | ≥ 1.24 | |
| SciPy | ≥ 1.11 | SPADE SVD |
| h5py | ≥ 3.9 | Checkpoint reading |
| Jinja2 | ≥ 3.1 | Julia driver templating |
| Julia | ≥ 1.11 | Required for CMF and TPSCI |
| TPSChem.jl | latest | Downloaded and built on first launch |

---

## Installation

### 1. Clone this repository

```bash
git clone https://github.com/arnab82/TPSChemVIS.git
cd TPSChemVIS
```

VibeMol is downloaded automatically on first launch to `~/.asbuilder/vibemol`.
Jmol is installed only when you choose **Jmol** in the viewer and click **Install Jmol**; the app downloads the official binary zip, extracts `Jmol.jar` to `~/.asbuilder/jmol/`, and launches it with Java.

### 2. Install Python dependencies

```bash
pip install -e .
```

This installs all Python dependencies and registers the `asbuilder` command.

### 3. Install Julia

Download Julia 1.11+ from [julialang.org](https://julialang.org/downloads/) or via `juliaup`:

```bash
curl -fsSL https://install.julialang.org | sh
```

### 4. Launch — first-run bootstrap handles the rest

```bash
asbuilder
```

On first launch TPSChemVIS automatically:

- downloads VibeMol to `~/.asbuilder/vibemol`;
- clones or updates `https://github.com/arnab82/TPSChem.jl.git` into `~/.asbuilder/TPSChem.jl`;
- runs `Pkg.instantiate`, builds PyCall against the same Python used by `pip install -e .`, and precompiles the Julia environment.

The configured path is saved to `~/.asbuilder/config.json` — subsequent launches skip the wizard entirely.

To point at a different TPSChem.jl clone or rebuild the Julia environment, use **Tools → Julia / TPSChem.jl setup…**.

---

## Usage

### Starting a new project

```bash
asbuilder ~/my_calculations/h6_project.qcproj
```

If the directory doesn't exist it is created automatically.

### Typical workflow

```text
Load checkpoint (.chk)
  ↓
Visualize MOs (VibeMol or Jmol)
  ↓
Define clusters
  ├── Manual mode  — click MO rows to assign to clusters
  └── SPADE mode   — assign atoms per cluster; select AO types (s/p/d/f)
  ↓
Build Active Space  →  inspect cluster moldens, verify n_α / n_β
  ↓
Run CMF (Newton / BFGS / DIIS)
  ↓
Run TPSCI / SPT / PT2 / CEPA  →  local or package for HPC
  ↓
Post-Analysis of wavefunction  →  CT arrow map, root-total chart, and sector-weight visualization
```

### Resuming from a saved calculation

From the **Load** screen:

- **Jump to CMF** — enabled automatically when `active_space/h0.npy` and `clusters.json` are found.
- **Jump to TPSCI/Export** — enabled automatically when `cmf/cmf_result.jld2` is found.

Use the **Browse** buttons to load intermediate results from a different project directory.

### SPADE mode (bimetallic / fragment systems)

Switch to the **SPADE — assign atoms** tab in the Clusters screen.  
Click atom rows to assign atoms to clusters. For each cluster, check which AO types (s / p / d / f) should contribute to the SPADE projector — useful for, e.g., assigning only Fe 3d orbitals to a metal cluster.

---

## Command-line options

```text
asbuilder [project_dir] [options]

Arguments:
  project_dir          Project folder (default: ~/asbuilder_projects/untitled.qcproj)

Options:
  --julia-bin PATH     Julia executable (default: julia from PATH)
  --julia-project PATH Override TPSChem.jl directory (saved to config)
  --vibemol-root PATH  Path to a custom VibeMol build
  --viewer vibemol|jmol
                      Default orbital viewer for this launch
  --jmol-command PATH Java executable or launcher command for desktop Jmol
  --setup              Force the TPSChem.jl setup dialog even if already configured
```

---

## Project directory layout

After a full run, a project folder looks like:

```text
my_project.qcproj/
├── project.json           # stage tracker
├── input.chk              # PySCF checkpoint (copied on load)
├── orbitals.molden        # canonical MO molden
├── clusters.json          # cluster definitions
├── active_space/
│   ├── h0.npy             # core energy
│   ├── h1.npy             # one-electron integrals
│   ├── h2.npy             # two-electron integrals
│   ├── Cact.molden        # all active MOs
│   ├── cluster_1_name.molden
│   ├── cluster_2_name.molden
│   └── cluster_map.json
├── cmf/
│   ├── driver_cmf.jl      # rendered CMF driver
│   └── cmf_result.jld2    # CMF output bundle
├── export/
    ├── driver_tpsci.jl    # rendered TPSCI driver
    └── export.log
└── post_analysis/
    ├── ct_analysis.txt
    ├── ct_table.csv
    ├── ct_sectors.csv
    └── wavefunction_post_analysis.jld2
```

---

## HPC / SLURM submission

The **TPSCI/Export** screen generates a `submit.slurm` script alongside the Julia driver. Fill in the job name, account, partition, nodes, and walltime, click **Package for HPC…** to download a `.zip` containing everything needed to run on a cluster.

---

## Dependencies and licenses

| Package | License | Notes |
| ------- | ------- | ----- |
| [PySCF](https://github.com/pyscf/pyscf) | Apache 2.0 | SCF and integral back-end |
| [VibeMol](https://github.com/evangelistalab/vibemol) | MIT | 3D orbital viewer (downloaded on first launch) |
| [Jmol](https://jmol.sourceforge.net/) | LGPL 2.0 | Optional desktop molecular viewer (installed on demand) |
| [TPSChem.jl](https://github.com/arnab82/TPSChem.jl) | See repo | CMF / TPSCI / SPT engine |
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GPL v3 | GUI framework |

---

## Contributing

Pull requests are welcome. The Python back-end (`asbuilder/active_space/`, `asbuilder/cluster/`, `asbuilder/julia_bridge/`) has no Qt dependency and can be tested in isolation. The GUI (`asbuilder/gui/`) requires a display.

```bash
# Run the app from source
pip install -e .
asbuilder
```

---

## Citation

If you use TPSChemVIS in your research, please cite the underlying TPSChem.jl methodology (see the TPSChem.jl repository for the appropriate references).
