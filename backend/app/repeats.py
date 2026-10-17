from datetime import date

import pandas as pd

from app.aircraft import same_aircraft_type
from app.sdr import repeat_groups
from app.vocab import ata_name


def first_value(series):
    """First value that is not empty, or None."""
    values = series.dropna()
    return values.iloc[0] if len(values) else None


def component_rows(cards, group_by="component", min_count=2):
    """Repeats grouped by component (the older rule, used for group_by=component)."""
    if not cards:
        return []

    df = pd.DataFrame(cards)
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df["downtime_hours"] = pd.to_numeric(df["downtime_hours"], errors="coerce")

    key = "registration" if group_by == "aircraft" else "component"

    df = df[df[key].notna() & df["failure_mode"].notna()]
    df = df[df["failure_mode"] != "other"]

    rows = []
    for (asset, mode), group in df.groupby([key, "failure_mode"]):
        if len(group) < min_count:
            continue

        group = group.sort_values("date_parsed")

        dates = group["date_parsed"].dropna()
        mtbf = None
        if len(dates) >= 2:
            mtbf = round(float(dates.diff().dropna().dt.days.mean()), 1)

        chapter = first_value(group["ata_chapter"])
        aircraft_type = first_value(group["aircraft_type"])

        rows.append({
            "asset": str(asset),
            "aircraft_type": None if aircraft_type is None else str(aircraft_type),
            "ata_chapter": None if chapter is None else str(chapter),
            "ata_name": ata_name(None if chapter is None else str(chapter)),
            "failure_mode": str(mode),
            "count": int(len(group)),
            "mtbf_days": mtbf,
            "downtime_hours": round(float(group["downtime_hours"].sum()), 1),
            "card_ids": [str(i) for i in group["id"]],
        })

    rows.sort(key=lambda r: (r["downtime_hours"], r["count"]), reverse=True)
    return rows


def event_dates(dates, min_gap_days):
    """Keep a date only if it is at least min_gap_days after the last kept one."""
    events, last = [], None
    for d in sorted(dates):
        if last is None or (d - last).days >= min_gap_days:
            events.append(d)
            last = d
    return events


def repeat_rows(cards, group_by="aircraft", min_count=2, min_gap_days=7):
    """The agreed rule: same tail + ATA chapter + failure mode, reports 7+ days apart."""
    if group_by != "aircraft":
        return component_rows(cards, group_by, min_count)

    by_id = {c["id"]: c for c in cards}
    rows = []
    for g in repeat_groups(cards, min_count, min_gap_days):
        members = [by_id[i] for i in g["card_ids"]]
        events = event_dates([date.fromisoformat(c["date"]) for c in members], min_gap_days)

        # MTBF = average number of days between the counted failures
        mtbf = None
        if len(events) >= 2:
            mtbf = round((events[-1] - events[0]).days / (len(events) - 1), 1)

        hours = sum(
            c["downtime_hours"] for c in members
            if isinstance(c.get("downtime_hours"), (int, float))
        )
        rows.append({
            "asset": g["asset"],
            "aircraft_type": g["aircraft_type"],
            "ata_chapter": g["ata_chapter"],
            "ata_name": g["ata_name"],
            "failure_mode": g["failure_mode"],
            "count": g["count"],
            "mtbf_days": mtbf,
            "downtime_hours": round(float(hours), 1),
            "card_ids": g["card_ids"],
        })

    # The contract says: ranked by downtime, then count
    rows.sort(key=lambda r: (-r["downtime_hours"], -r["count"], r["asset"]))
    return rows


def repeat_history(cards, failure_mode, asset=None, aircraft_type=None):
    """Earlier cards with the same failure mode on this asset, or aircraft type, or the fleet."""
    if failure_mode == "other":
        return None
    same = [c for c in cards if c.get("failure_mode") == failure_mode]
    if asset:
        same = [c for c in same if c.get("registration") == asset]
    elif aircraft_type:
        same = [c for c in same if same_aircraft_type(c.get("aircraft_type"), aircraft_type)]
    if not same:
        return None
    dates = sorted(c["date"] for c in same if c.get("date"))
    return {
        "count": len(same),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "card_ids": [c["id"] for c in same][:50],
    }