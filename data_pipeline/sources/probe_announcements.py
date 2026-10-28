"""Check whether CNINFO supplies historical announcements for one stock."""

import argparse
import json
from pathlib import Path

import akshare as ak


RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", default="300750")
    parser.add_argument("--start", default="20250101")
    parser.add_argument("--end", default="20250331")
    args = parser.parse_args()

    announcements = ak.stock_zh_a_disclosure_report_cninfo(
        symbol=args.stock,
        market="沪深京",
        start_date=args.start,
        end_date=args.end,
    )
    expected = {"代码", "公告标题", "公告时间", "公告链接"}
    if not announcements.empty and not expected.issubset(announcements.columns):
        raise ValueError(f"Unexpected announcement columns: {announcements.columns.tolist()}")
    RAW.mkdir(parents=True, exist_ok=True)
    announcements.to_csv(
        RAW / f"{args.stock}_announcements_{args.start}_{args.end}.csv",
        index=False,
        encoding="utf-8-sig",
    )
    dates = (
        sorted(str(value) for value in announcements["公告时间"].dropna())
        if not announcements.empty
        else []
    )
    samples = (
        announcements[["公告标题", "公告链接"]].head(3).to_dict("records")
        if not announcements.empty
        else []
    )
    print(
        json.dumps(
            {
                "stock": args.stock,
                "period": [args.start, args.end],
                "rows": len(announcements),
                "date_range": [dates[0], dates[-1]] if dates else [None, None],
                "columns": announcements.columns.tolist(),
                "sample_titles_and_links": samples,
                "body_available_in_table": "公告正文" in announcements.columns,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
