"""Audit historical announcement coverage and a small PDF text sample."""

import argparse
import csv
import io
import json
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from pypdf import PdfReader

from .collect_announcements import RAW, STOCKS, quarters


ROOT = RAW.parent.parent
PROCESSED = ROOT / "data" / "processed"
PDF_DIR = RAW / "announcement_pdfs"
MAX_PDF_BYTES = 12_000_000


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_announcements(stock, start, end):
    rows = {}
    checks = Counter()
    for first, last in quarters(start, end):
        path = RAW / f"{stock}_announcements_{first:%Y%m%d}_{last:%Y%m%d}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}; run collect_announcements.py first")
        for row in read_csv(path):
            checks["raw_rows"] += 1
            if not row["公告时间"] or not row["公告链接"]:
                checks["missing_time_or_link"] += 1
                continue
            published = datetime.fromisoformat(row["公告时间"]).date()
            if not start <= published <= end:
                checks["out_of_period"] += 1
                continue
            if row["代码"].zfill(6) != stock:
                raise ValueError(f"Unexpected stock code in {path}: {row['代码']}")
            key = parse_qs(urlparse(row["公告链接"]).query).get("announcementId")
            key = key[0] if key else row["公告链接"]
            checks["duplicate_ids"] += key in rows
            rows[key] = row
    ordered = sorted(rows.values(), key=lambda row: (row["公告时间"], row["公告链接"]))
    return ordered, {
        name: checks[name]
        for name in ("raw_rows", "missing_time_or_link", "out_of_period", "duplicate_ids")
    }


def coverage(stock, rows, start, end):
    prices = read_csv(RAW / f"{stock}_prices_probe.csv")
    trading_days = sorted(date.fromisoformat(row["日期"]) for row in prices)
    period_days = {day for day in trading_days if start <= day <= end}
    assigned = Counter()
    date_only = 0
    shifted = 0
    for row in rows:
        published = datetime.fromisoformat(row["公告时间"])
        day = published.date()
        unknown_time = published.time() == time.min
        after_close = published.time() >= time(15)
        position = (
            bisect_right(trading_days, day)
            if unknown_time or after_close
            else bisect_left(trading_days, day)
        )
        date_only += unknown_time
        if position < len(trading_days):
            target = trading_days[position]
            shifted += target != day
            if target in period_days:
                assigned[target] += 1
    by_year = {}
    for year in range(start.year, end.year + 1):
        year_days = {day for day in period_days if day.year == year}
        covered = sum(day in assigned for day in year_days)
        by_year[str(year)] = {
            "announcements": sum(row["公告时间"].startswith(str(year)) for row in rows),
            "trading_days": len(year_days),
            "covered_trading_days": covered,
            "coverage_percent": round(100 * covered / len(year_days), 2)
            if year_days else None,
        }
    return {
        "announcements": len(rows),
        "date_only_timestamps": date_only,
        "shifted_to_later_trading_day": shifted,
        "trading_days": len(period_days),
        "covered_trading_days": len(assigned),
        "coverage_percent": round(100 * len(assigned) / len(period_days), 2)
        if period_days else None,
        "maximum_announcements_on_one_trading_day": max(assigned.values(), default=0),
        "by_year": by_year,
    }


def pdf_url(row):
    published = datetime.fromisoformat(row["公告时间"])
    ids = parse_qs(urlparse(row["公告链接"]).query).get("announcementId")
    if not ids or not ids[0].isdigit():
        raise ValueError("Announcement ID missing from detail link")
    return f"https://static.cninfo.com.cn/finalpage/{published:%Y-%m-%d}/{ids[0]}.PDF", ids[0]


def inspect_pdf(stock, row):
    url, announcement_id = pdf_url(row)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = PDF_DIR / f"{stock}_{announcement_id}.pdf"
    if path.exists():
        content = path.read_bytes()
    else:
        with requests.get(url, timeout=30, stream=True) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(chunk_size=65536):
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise ValueError("PDF exceeds 12 MB sampling limit")
                chunks.append(chunk)
        content = b"".join(chunks)
        if not content.startswith(b"%PDF"):
            raise ValueError("Response is not a PDF")
        path.write_bytes(content)
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:3])
    chinese_characters = len(re.findall(r"[\u4e00-\u9fff]", text))
    extracted_characters = len(text.strip())
    return {
        "stock": stock,
        "published_at": row["公告时间"],
        "title": row["公告标题"],
        "url": url,
        "pages": len(reader.pages),
        "sampled_pages": min(len(reader.pages), 3),
        "extracted_characters": extracted_characters,
        "chinese_characters": chinese_characters,
        "text_extractable": extracted_characters >= 100,
        "usable_chinese_text": chinese_characters >= 100,
        "saved_to": str(path.relative_to(ROOT)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stocks", nargs="+", default=STOCKS, choices=STOCKS)
    parser.add_argument("--start", default="20230101")
    parser.add_argument("--end", default="20251231")
    parser.add_argument("--pdf-per-stock-year", type=int, default=1)
    parser.add_argument("--skip-pdf", action="store_true")
    args = parser.parse_args()
    start = datetime.strptime(args.start, "%Y%m%d").date()
    end = datetime.strptime(args.end, "%Y%m%d").date()
    if start > end or args.pdf_per_stock_year < 0:
        parser.error("Invalid date range or PDF sample count")

    result = {"period": [args.start, args.end], "stocks": {}, "pdf_samples": []}
    for stock in args.stocks:
        rows, checks = load_announcements(stock, start, end)
        result["stocks"][stock] = {**coverage(stock, rows, start, end), **checks}
        print(json.dumps({stock: result["stocks"][stock]}, ensure_ascii=False), flush=True)
        if args.skip_pdf:
            continue
        for year in range(start.year, end.year + 1):
            year_rows = [row for row in rows if row["公告时间"].startswith(str(year))]
            sample_count = min(args.pdf_per_stock_year, len(year_rows))
            for index in range(sample_count):
                row = year_rows[(index + 1) * len(year_rows) // (sample_count + 1)]
                try:
                    sample = inspect_pdf(stock, row)
                except Exception as error:
                    sample = {
                        "stock": stock,
                        "published_at": row["公告时间"],
                        "title": row["公告标题"],
                        "error": f"{type(error).__name__}: {error}",
                        "text_extractable": False,
                        "usable_chinese_text": False,
                    }
                result["pdf_samples"].append(sample)
                print(json.dumps({"pdf_sample": sample}, ensure_ascii=False), flush=True)

    samples = result["pdf_samples"]
    result["pdf_summary"] = {
        "sampled": len(samples),
        "text_extractable": sum(sample["text_extractable"] for sample in samples),
        "usable_chinese_text": sum(sample["usable_chinese_text"] for sample in samples),
        "errors": sum("error" in sample for sample in samples),
    }
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / f"announcement_audit_{args.start}_{args.end}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved_to": str(path.relative_to(ROOT)), **result["pdf_summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
