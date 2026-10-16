import pandas as pd

from app.vocab import ata_name


def first_value(series):
    """First value that is not empty, or None."""
    values = series.dropna()
    return values.iloc[0] if len(values) else None


def repeat_rows(cards, group_by="aircraft", min_count=2):
    """Find failures that keep coming back on the same aircraft (or component)."""
    if not cards:
        return []

    df = pd.DataFrame(cards)
    df["date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df["downtime_hours"] = pd.to_numeric(df["downtime_hours"], errors="coerce")

    # What we group by: the tail number, or the component name
    key = "registration" if group_by == "aircraft" else "component"

    # Skip cards with no tail number/component, and the vague "other" failure mode
    df = df[df[key].notna() & df["failure_mode"].notna()]
    df = df[df["failure_mode"] != "other"]

    rows = []
    for (asset, mode), group in df.groupby([key, "failure_mode"]):
        if len(group) < min_count:
            continue

        group = group.sort_values("date_parsed")

        # MTBF = average number of days between one failure and the next
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

    # Biggest downtime first, then highest count (this is the Pareto order)
    rows.sort(key=lambda r: (r["downtime_hours"], r["count"]), reverse=True)
    return rows

def repeat_history(cards, failure_mode, asset=None):
    """Earlier cards with the same failure mode on this asset (or the whole fleet)."""
    if failure_mode == "other":
        return None
    same = [c for c in cards if c.get("failure_mode") == failure_mode]
    if asset:
        same = [c for c in same if c.get("registration") == asset]
    if not same:
        return None
    dates = sorted(c["date"] for c in same if c.get("date"))
    return {
        "count": len(same),
        "first_date": dates[0] if dates else None,
        "last_date": dates[-1] if dates else None,
        "card_ids": [c["id"] for c in same][:50],  # the list is capped at 50, count is the full number
    }