"""
Cluster assignment data model.

Mirrors TPSChem.jl's ``MOCluster`` contract exactly: a cluster is an id plus
a list of 1-based molecular-orbital indices, and CMF additionally needs an
``init_fspace = (n_alpha, n_beta)`` per cluster. See
``TPSChem.jl/src/QCBase/README.md`` and ``test/test_direct_cmf.jl``:

    clusters    = [MOCluster(1, [1,2,3,4]), MOCluster(2, [5,6,7,8])]
    init_fspace = [(2,2), (2,2)]

Two ways a cluster's `orbitals` list gets filled in, both supported here:

1. Manual: the user clicks individual orbitals in the viewer and assigns
   them one at a time (Tier A/B UI from the design doc).
2. SPADE-partitioned: the user assigns *atoms* to a cluster (defining a
   fragment), and `asbuilder.active_space.localize_integrals` runs the SVD
   subspace partitioning to automatically fill in `orbitals` from atom
   membership + a chosen (NDocc, NAct, Nvirt) split. In that case
   `atom_indices` and `dims` are populated as the *input* to partitioning,
   and `orbitals` is filled in as its *output*.

Both are legal; `orbitals` is always what ends up in `clusters.json` and is
the only field TPSChem.jl actually consumes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

CLUSTERS_FILE = "clusters.json"

# A palette cycled through when auto-assigning colors to new clusters in the
# GUI's cluster manager. Kept here (not in Qt code) so both the widget and
# any headless script agree on the same colors for a given cluster id.
DEFAULT_COLORS = [
    "#e6194B", "#3cb44b", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45",
    "#fabed4", "#469990", "#dcbeff", "#9A6324",
]


@dataclass
class Cluster:
    id: int
    name: str = ""
    color: str = ""
    orbitals: list[int] = field(default_factory=list)   # 1-based MO indices (final)
    fspace: tuple[int, int] = (0, 0)                     # (n_alpha, n_beta)
    atom_indices: Optional[list[int]] = None             # SPADE fragment input (0-based atoms)
    ao_types: list[str] = field(default_factory=list)    # SPADE AO type filter, e.g. ["d","f"]; empty = all
    dims: Optional[tuple[int, int, int]] = None           # SPADE (NDocc, NAct, Nvirt) input

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"cluster{self.id}"
        if not self.color:
            self.color = DEFAULT_COLORS[(self.id - 1) % len(DEFAULT_COLORS)]

    @property
    def n_orb(self) -> int:
        return len(self.orbitals)

    @property
    def n_elec(self) -> int:
        return sum(self.fspace)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "orbitals": list(self.orbitals),
            "fspace": list(self.fspace),
            "atom_indices": self.atom_indices,
            "ao_types": list(self.ao_types),
            "dims": list(self.dims) if self.dims is not None else None,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Cluster":
        return cls(
            id=d["id"],
            name=d.get("name", ""),
            color=d.get("color", ""),
            orbitals=list(d.get("orbitals", [])),
            fspace=tuple(d.get("fspace", (0, 0))),
            atom_indices=d.get("atom_indices"),
            ao_types=list(d.get("ao_types", [])),
            dims=tuple(d["dims"]) if d.get("dims") is not None else None,
        )


class ClusterSet:
    """An ordered collection of Clusters, with validation and clusters.json
    read/write. This is what the GUI's cluster manager panel binds to."""

    def __init__(self, clusters: Optional[list[Cluster]] = None) -> None:
        self.clusters: list[Cluster] = clusters or []

    # -- CRUD used by the cluster-manager dock widget ----------------------

    def add_cluster(self, name: str = "") -> Cluster:
        next_id = max((c.id for c in self.clusters), default=0) + 1
        c = Cluster(id=next_id, name=name)
        self.clusters.append(c)
        return c

    def remove_cluster(self, cluster_id: int) -> None:
        self.clusters = [c for c in self.clusters if c.id != cluster_id]

    def get(self, cluster_id: int) -> Cluster:
        for c in self.clusters:
            if c.id == cluster_id:
                return c
        raise KeyError(f"no cluster with id {cluster_id}")

    def assign_atom(self, cluster_id: int, atom_index: int) -> None:
        """Assign a 0-based atom index to a cluster (SPADE mode), removing from any other first."""
        for c in self.clusters:
            if c.atom_indices and atom_index in c.atom_indices:
                c.atom_indices.remove(atom_index)
        target = self.get(cluster_id)
        if target.atom_indices is None:
            target.atom_indices = []
        if atom_index not in target.atom_indices:
            target.atom_indices.append(atom_index)

    def unassign_atom(self, atom_index: int) -> None:
        for c in self.clusters:
            if c.atom_indices and atom_index in c.atom_indices:
                c.atom_indices.remove(atom_index)

    def assign_orbital(self, cluster_id: int, orbital_index: int) -> None:
        """Assign a single (1-based) orbital index to a cluster, removing it
        from any other cluster first so an orbital only ever belongs to one
        cluster at a time -- this is what a click-to-assign UI action maps
        to directly."""
        for c in self.clusters:
            if orbital_index in c.orbitals:
                c.orbitals.remove(orbital_index)
        self.get(cluster_id).orbitals.append(orbital_index)

    def unassigned_orbitals(self, total_orbitals: int) -> list[int]:
        assigned = {o for c in self.clusters for o in c.orbitals}
        return [i for i in range(1, total_orbitals + 1) if i not in assigned]

    # -- validation ---------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of human-readable problems, empty if none. The GUI
        should keep "Build Active Space" disabled while this is non-empty."""
        problems = []
        if not self.clusters:
            problems.append("no clusters defined")
        seen: dict[int, int] = {}
        spade = any(c.atom_indices is not None for c in self.clusters)
        for c in self.clusters:
            if not spade and not c.orbitals:
                problems.append(f"cluster {c.id} ({c.name}) has no orbitals assigned")
            if spade and not c.atom_indices:
                problems.append(f"cluster {c.id} ({c.name}) has no atoms assigned (SPADE mode)")
            if not spade and sum(c.fspace) == 0:
                problems.append(f"cluster {c.id} ({c.name}) has no electrons set (n_alpha, n_beta)")
            if any(x < 0 for x in c.fspace):
                problems.append(f"cluster {c.id} ({c.name}) has a negative electron count")
            for o in c.orbitals:
                seen[o] = seen.get(o, 0) + 1
        dupes = [o for o, n in seen.items() if n > 1]
        if dupes:
            problems.append(f"orbitals assigned to more than one cluster: {sorted(dupes)}")
        return problems

    # -- TPSChem.jl contract --------------------------------------------------

    def as_mocluster_literal(self) -> str:
        """Render as a Julia literal matching QCBase.MOCluster, for direct
        interpolation into a Jinja2 driver-script template, e.g.:

            clusters = [MOCluster(1,[1,2,3,4]), MOCluster(2,[5,6,7,8])]
        """
        parts = [f"MOCluster({c.id},[{','.join(str(o) for o in c.orbitals)}])" for c in self.clusters]
        return "[" + ", ".join(parts) + "]"

    def as_init_fspace_literal(self) -> str:
        """Render as a Julia literal matching the init_fspace convention,
        e.g.: init_fspace = [(2,2), (2,2), (2,2)]"""
        parts = [f"({c.fspace[0]},{c.fspace[1]})" for c in self.clusters]
        return "[" + ", ".join(parts) + "]"

    def as_ansatze_literal(self) -> str:
        """Render FCIAnsatz objects for cmf_oo_newton, e.g.:
        [FCIAnsatz(5,3,0), FCIAnsatz(3,3,3), FCIAnsatz(5,3,0)]"""
        parts = [f"FCIAnsatz({c.n_orb},{c.fspace[0]},{c.fspace[1]})" for c in self.clusters]
        return "[" + ", ".join(parts) + "]"

    # -- persistence ----------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps([c.to_dict() for c in self.clusters], indent=2)

    def save(self, project_root: Path) -> Path:
        problems = self.validate()
        path = Path(project_root) / CLUSTERS_FILE
        path.write_text(self.to_json())
        return path

    @classmethod
    def load(cls, project_root: Path) -> "ClusterSet":
        path = Path(project_root) / CLUSTERS_FILE
        data = json.loads(path.read_text())
        return cls([Cluster.from_dict(d) for d in data])
