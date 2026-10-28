"""Download referenced CNINFO PDFs and save extractable announcement text."""

import argparse
import csv
import io
import json
import re
import time
from collections import Counter
from datetime import date
from urllib.parse import parse_qs, urlparse

import requests
import pdfplumber
from pypdf import PdfReader

from data_pipeline.sources.audit_announcements import PDF_DIR, PROCESSED, ROOT, load_announcements, pdf_url


SAMPLES = PROCESSED / "daily_samples_2023_2025.csv"
TEXT_DIR = PROCESSED / "announcement_texts"
MAX_PDF_BYTES = 30_000_000
MAX_PAGES = 10
MAX_CHARACTERS = 20_000


def read_samples():
    with SAMPLES.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def selected_ids(split):
    selected = set()
    for row in read_samples():
        if split == "all" or row["split"] == split:
            selected.update(row["announcement_ids"].split("|"))
    selected.discard("")
    return selected


def referenced_announcements(split):
    ids = selected_ids("train" if split == "pilot" else split)
    found = {}
    for stock in ("300750", "002594", "300059", "600519", "000001"):
        rows, _ = load_announcements(stock, date(2023, 1, 1), date(2025, 12, 31))
        for row in rows:
            query = parse_qs(urlparse(row["公告链接"]).query)
            announcement_id = query.get("announcementId", [None])[0]
            if announcement_id in ids:
                found[announcement_id] = (stock, row)
    missing = ids - found.keys()
    if missing:
        raise ValueError(f"Sample IDs not found in announcement snapshots: {sorted(missing)[:5]}")
    return found


def choose_pilot(found):
    groups = {}
    for announcement_id, (stock, row) in found.items():
        year = row["公告时间"][:4]
        groups.setdefault((stock, year), []).append((announcement_id, stock, row))
    chosen = []
    for group in sorted(groups):
        entries = sorted(groups[group], key=lambda item: (item[2]["公告时间"], item[0]))
        count = min(5, len(entries))
        chosen.extend(entries[(index + 1) * len(entries) // (count + 1)] for index in range(count))
    return chosen


def download_pdf(stock, announcement_id, url):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    path = PDF_DIR / f"{stock}_{announcement_id}.pdf"
    if path.exists():
        return path.read_bytes(), path, url
    candidates = (url, url[:-4] + ".pdf") if url.endswith(".PDF") else (url,)
    for candidate in candidates:
        with requests.get(candidate, timeout=(10, 30), stream=True) as response:
            if response.status_code == 404 and candidate != candidates[-1]:
                continue
            response.raise_for_status()
            declared_size = response.headers.get("Content-Length")
            if declared_size and int(declared_size) > MAX_PDF_BYTES:
                raise ValueError("PDF exceeds 30 MB limit")
            parts = []
            size = 0
            for part in response.iter_content(chunk_size=65536):
                size += len(part)
                if size > MAX_PDF_BYTES:
                    raise ValueError("PDF exceeds 30 MB limit")
                parts.append(part)
        break
    content = b"".join(parts)
    if not content.startswith(b"%PDF"):
        raise ValueError("Response is not a PDF")
    temporary = path.with_suffix(".pdf.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)
    return content, path, candidate


def extract_one(announcement_id, stock, row):
    url, _ = pdf_url(row)
    result = {
        "announcement_id": announcement_id,
        "stock": stock,
        "published_at": row["公告时间"],
        "title": row["公告标题"],
        "detail_url": row["公告链接"],
        "pdf_url": url,
    }
    try:
        content, path, resolved_url = download_pdf(stock, announcement_id, url)
        result["pdf_url"] = resolved_url
        reader = PdfReader(io.BytesIO(content))
        pages = min(len(reader.pages), MAX_PAGES)
        text = "\n".join(reader.pages[index].extract_text() or "" for index in range(pages))
        extractor = "pypdf"
        if len(re.findall(r"[\u4e00-\u9fff]", text)) < 100:
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                alternative = "\n".join(page.extract_text() or "" for page in pdf.pages[:MAX_PAGES])
            if len(re.findall(r"[\u4e00-\u9fff]", alternative)) > len(
                re.findall(r"[\u4e00-\u9fff]", text)
            ):
                text, extractor = alternative, "pdfplumber"
        text = text.strip()[:MAX_CHARACTERS]
        chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
        result.update(
            {
                "status": "usable_chinese" if chinese >= 100 else "insufficient_chinese" if len(text) >= 100 else "little_text",
                "pdf_bytes": len(content),
                "pages": len(reader.pages),
                "extracted_pages": pages,
                "extractor": extractor,
                "extracted_characters": len(text),
                "chinese_characters": chinese,
                "pdf_path": str(path.relative_to(ROOT)),
                "text": text,
            }
        )
    except Exception as error:
        result.update({"status": "error", "error": f"{type(error).__name__}: {error}", "text": ""})
    return result


def save_result(result):
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = TEXT_DIR / f"{result['announcement_id']}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("pilot", "train", "validation", "test", "all"), default="pilot")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--delay", type=float, default=0.5)
    retry = parser.add_mutually_exclusive_group()
    retry.add_argument("--retry-unusable", action="store_true")
    retry.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()
    if (args.limit is not None and args.limit < 1) or args.delay < 0:
        parser.error("--limit must be positive and --delay must not be negative")

    found = referenced_announcements(args.split)
    entries = (
        choose_pilot(found)
        if args.split == "pilot"
        else [(announcement_id, *found[announcement_id]) for announcement_id in sorted(found)]
    )
    if args.limit is not None:
        entries = entries[: args.limit]
    manifest = []
    for index, (announcement_id, stock, row) in enumerate(entries, start=1):
        path = TEXT_DIR / f"{announcement_id}.json"
        processed = False
        if path.exists():
            result = json.loads(path.read_text(encoding="utf-8"))
            if (args.retry_unusable and result["status"] != "usable_chinese") or (
                args.retry_errors and result["status"] == "error"
            ):
                result = extract_one(announcement_id, stock, row)
                save_result(result)
                processed = True
        else:
            result = extract_one(announcement_id, stock, row)
            save_result(result)
            processed = True
        manifest.append({key: value for key, value in result.items() if key != "text"})
        print(json.dumps({"index": index, "total": len(entries), "id": announcement_id, "status": result["status"]}, ensure_ascii=False), flush=True)
        if index < len(entries) and processed:
            time.sleep(args.delay)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    output = PROCESSED / f"announcement_text_manifest_{args.split}.json"
    summary = {
        "split": args.split,
        "selected": len(entries),
        "status_counts": dict(Counter(item["status"] for item in manifest)),
        "results": manifest,
    }
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"saved_to": str(output.relative_to(ROOT)), "selected": len(entries), "status_counts": summary["status_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
