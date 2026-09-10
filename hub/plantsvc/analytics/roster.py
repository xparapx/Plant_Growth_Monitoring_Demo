"""Which pots exist, which treatment each has, and where the two label sources disagree.

soil.treat comes from the watering firmware; growth.treat comes from
config.json rois[].treat.  If they differ for one pot, one of them is wrong
and the data cannot tell which - so that pot is excluded from every chart and
listed for a human (the "07-28 incident").
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from ..config_model import TREATS


def roster_of(*dfs: pd.DataFrame) -> dict[str, str]:
    fr = [d[["plant_id", "treat"]] for d in dfs if len(d) and "plant_id" in d.columns]
    if not fr:
        return {}
    return pd.concat(fr).dropna().groupby("plant_id").treat.last().to_dict()


def treat_sources(soil: pd.DataFrame, grow: pd.DataFrame) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for src, d in (("soil", soil), ("growth", grow)):
        if len(d) and "plant_id" in d.columns:
            last = d[["plant_id", "treat"]].dropna().groupby("plant_id").treat.last()
            for pid, tr in last.items():
                out.setdefault(str(pid), {})[src] = str(tr)
    return out


@dataclass
class Roster:
    treat: dict[str, str] = field(default_factory=dict)        # after unknown/conflict removal
    pots: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)   # only non-empty groups
    unknown: list[str] = field(default_factory=list)
    conflicts: dict[str, dict[str, str]] = field(default_factory=dict)
    sources: dict[str, dict[str, str]] = field(default_factory=dict)

    @property
    def ncol(self) -> int:
        return max((len(v) for v in self.groups.values()), default=1)

    def group_of(self, pid: str) -> str | None:
        return self.treat.get(pid)

    def suggested_sql(self) -> str | None:
        if not self.unknown:
            return None
        labels = ", ".join(repr(u) for u in self.unknown)
        return f"DELETE FROM soil WHERE treat IN ({labels});"


def build_roster(soil: pd.DataFrame, grow: pd.DataFrame) -> Roster:
    treat = {str(k): str(v) for k, v in roster_of(soil, grow).items()}
    unknown = sorted({v for v in treat.values() if v not in TREATS})
    if unknown:
        treat = {k: v for k, v in treat.items() if v in TREATS}
    sources = treat_sources(soil, grow)
    conflicts = {p: v for p, v in sources.items() if len(set(v.values())) > 1}
    if conflicts:
        treat = {k: v for k, v in treat.items() if k not in conflicts}
    pots = sorted(treat)
    groups = {t: [p for p in pots if treat.get(p) == t] for t in TREATS}
    groups = {t: v for t, v in groups.items() if v}
    return Roster(treat=treat, pots=pots, groups=groups, unknown=unknown,
                  conflicts=conflicts, sources=sources)
