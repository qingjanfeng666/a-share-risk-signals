"""Choose trading dates to score in a rolling thirty-day window."""


def dates_to_score(prices, first_date, existing):
    dates = [str(row["日期"])[:10] for row in prices]
    if first_date is None:
        return [(len(dates) - 1, dates[-1])]
    recent = range(max(19, len(dates) - 30), len(dates))
    latest = dates[-1]
    return [
        (index, dates[index]) for index in recent
        if dates[index] >= first_date
        and (dates[index] == latest or existing.get(dates[index]) != "ready")
    ]
