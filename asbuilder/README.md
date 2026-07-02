# Active Space Builder -- scaffold

See `active_space_gui_design.md` (one level up) for the full design writeup.
This is a working scaffold, not a finished app -- see "Known gaps" below for
exactly what's stubbed vs real.

## Setup

```bash
pip install PyQt6 PyQt6-WebEngine jinja2 numpy pyscf

# Vendor a local copy of VibeMol (MIT licensed) for the orbital viewer --
# keeps the app usable offline, no network access needed at runtime:
mkdir -p asbuilder/webview/vendor
git clone --depth 1 https://github.com/evangelistalab/vibemol asbuilder/webview/vendor/vibemol
```

Julia side (once, per machine/environment -- not per job):

```bash
julia --project=<your TPSChem.jl project> -e 'using Pkg; Pkg.build("PyCall")'
# only actually needed if a driver script does `using PyCall` (TPSChem.jl's
# "direct" PySCF-via-Julia mode) -- driver_cmf.jl.j2 as shipped doesn't.
```

## Run

```bash
python -m asbuilder.gui.app ./my_project.qcproj --julia-bin julia
```

## What's real vs stubbed

Tested against a live PySCF install in the environment this was built in
(4-atom H4 chain, sto-3g) -- see the smoke test transcript for the exact
run. The reconstructed total energy from the written h0/h1/h2 matched
PySCF's own E_tot exactly.

| Piece | Status |
|---|---|
| `project.py`, `cluster/state.py` | Real, tested |
| `io/chk_to_molden.py` | Real, tested against live PySCF |
| `active_space/localize_integrals.py`: SPADE functions | Your real code, wrapped verbatim |
| `active_space/localize_integrals.py`: `write_incore_ints` | Real, tested (energy check passed) |
| `active_space/localize_integrals.py`: `build_active_space` | **Stub (`NotImplementedError`)** -- needs the notebook's driver cells (how `Pv`/`dims` are built per cluster and how the SPADE functions compose) |
| `io/run_scf.py` | **Generic placeholder** (RHF/UHF/ROHF) -- needs your actual notebook's SCF setup for real systems |
| `julia_bridge/templates/*.jl.j2` | Verified against `TPSChem.jl`'s own test suite (`test_direct_cmf.jl`, `test_tpsci.jl`, `test_spt.jl`, `test_Clusters.jl`), not run against real Julia |
| GUI (`gui/`) | Syntax-checked and cross-checked against the real PyQt6/QtWebEngine API stubs; **not run** -- this dev sandbox is headless and can't install the system Qt libraries (libEGL etc.), so nothing here has actually been clicked through. Test on your machine first. |
| VibeMol drop-zone selector (`webview_panel.py: _DROP_TARGET_SELECTOR`) | Guessed (`"body"`) -- confirm against the vendored build's `index.html`/`file-loader.js` |
| Skipping CMF before export | Not wired up -- `driver_tpsci.jl.j2`/`driver_spt.jl.j2` currently assume a CMF-produced `cmf_result.jld2` bundle |

## Suggested next steps

1. Run it on your machine, click through Load -> Molden -> a real VibeMol
   pane, and fix `_DROP_TARGET_SELECTOR` if the simulated drop doesn't load
   the file.
2. Share the notebook's real SCF-setup cells and SPADE driver cells so
   `run_scf.py` and `build_active_space` stop being placeholders.
3. Try `driver_cmf.jl.j2` against a real Julia 1.11 + `TPSChem.jl`
   environment on a toy system (e.g. the H4 chain from the smoke test) to
   catch any API drift from what the test suite showed.
