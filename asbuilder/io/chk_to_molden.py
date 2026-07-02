"""
PySCF .chk -> .molden, and provenance extraction, for stage 1 of the pipeline.

Deliberately does NOT go through Gaussian/MOKIT/iodata: the project's
checkpoint is PySCF's own HDF5-based chkfile (``mf.chkfile = path;
mf.kernel()``), which PySCF can read back and convert to molden natively.
Verified against a live PySCF 2.13 install:

    from pyscf import lib
    from pyscf.tools import molden

    mol = lib.chkfile.load_mol(chk_path)
    d   = lib.chkfile.load(chk_path, "scf")   # {'e_tot','mo_coeff','mo_energy','mo_occ'}
    molden.from_mo(mol, out_path, d["mo_coeff"], ene=d["mo_energy"], occ=d["mo_occ"])

No MOKIT, no Gaussian, no iodata -- one PySCF-native round trip, so there's
one less place for MO ordering/sign conventions to drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class OrbitalInfo:
    """One row of the orbital table shown in the GUI (stage 2 dock panel)."""

    index: int          # 1-based, matches the convention MOCluster expects
    energy: float
    occupation: float


@dataclass
class ChkContents:
    mol: Any                 # pyscf.gto.Mole, reconstructed from the chk
    mo_coeff: np.ndarray      # (nao, nmo)
    mo_energy: np.ndarray     # (nmo,)
    mo_occ: np.ndarray        # (nmo,)
    e_tot: float
    method: str               # scf module key the data was stored under, e.g. "scf"

    @property
    def n_orb(self) -> int:
        return self.mo_coeff.shape[1]

    def orbital_table(self) -> list[OrbitalInfo]:
        return [
            OrbitalInfo(index=i + 1, energy=float(self.mo_energy[i]), occupation=float(self.mo_occ[i]))
            for i in range(self.n_orb)
        ]


def load_chk(chk_path: str | Path, scf_key: str = "scf") -> ChkContents:
    """Load a PySCF checkpoint written via `mf.chkfile = path; mf.kernel()`.

    `scf_key` is the group the data was dumped under -- "scf" for a plain
    mean-field run. If your notebook runs something else (e.g. a CASSCF on
    top, or dumps under a custom key), pass that key instead; the group is
    expected to contain at least mo_coeff/mo_energy/mo_occ.
    """
    from pyscf import lib

    chk_path = str(chk_path)
    mol = lib.chkfile.load_mol(chk_path)
    data = lib.chkfile.load(chk_path, scf_key)
    if data is None:
        raise ValueError(
            f"no {scf_key!r} group found in {chk_path}; pass scf_key= explicitly "
            "if this checkpoint was dumped under a different key"
        )
    missing = [k for k in ("mo_coeff", "mo_energy", "mo_occ") if k not in data]
    if missing:
        raise ValueError(f"{chk_path} is missing {missing} under group {scf_key!r}")

    return ChkContents(
        mol=mol,
        mo_coeff=np.asarray(data["mo_coeff"]),
        mo_energy=np.asarray(data["mo_energy"]),
        mo_occ=np.asarray(data["mo_occ"]),
        e_tot=float(data.get("e_tot", float("nan"))),
        method=scf_key,
    )


def write_molden(chk: ChkContents, out_path: str | Path) -> Path:
    """Write a .molden file VibeMol can load directly, from a loaded chk."""
    from pyscf.tools import molden

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    molden.from_mo(chk.mol, str(out_path), chk.mo_coeff, ene=chk.mo_energy, occ=chk.mo_occ)
    return out_path


def chk_to_molden(chk_path: str | Path, out_path: str | Path, scf_key: str = "scf") -> tuple[ChkContents, Path]:
    """Convenience wrapper: load + write in one call. Returns (chk, molden_path)
    so the caller (GUI worker thread) has both the orbital table data and the
    written file path without a second read."""
    chk = load_chk(chk_path, scf_key=scf_key)
    path = write_molden(chk, out_path)
    return chk, path


def provenance(chk: ChkContents) -> dict[str, Any]:
    """Read-only summary for the "Load" screen's provenance panel --
    displayed instead of asking the user to re-enter basis/charge/etc."""
    mol = chk.mol
    return {
        "formula": mol.atom.strip() if isinstance(mol.atom, str) else str(mol.atom),
        "basis": mol.basis if isinstance(mol.basis, str) else "custom/mixed",
        "charge": mol.charge,
        "spin": mol.spin,  # 2S, PySCF convention (n_alpha - n_beta)
        "n_atoms": mol.natm,
        "n_orb": chk.n_orb,
        "n_electrons": mol.nelectron,
        "e_tot": chk.e_tot,
        "method": chk.method,
    }
