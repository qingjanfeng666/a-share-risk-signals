"""Download one CNINFO announcement PDF and check extractable text."""

import argparse
import io
import json
from pathlib import Path

import requests
from pypdf import PdfReader


RAW = Path(__file__).resolve().parents[2] / "data" / "raw"
SAMPLE_URL = "https://static.cninfo.com.cn/finalpage/2025-03-25/1222897257.PDF"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=SAMPLE_URL)
    args = parser.parse_args()

    response = requests.get(args.url, timeout=30)
    response.raise_for_status()
    content = response.content
    if not content.startswith(b"%PDF"):
        raise ValueError(f"Response is not a PDF: {response.headers.get('Content-Type')}")

    reader = PdfReader(io.BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    RAW.mkdir(parents=True, exist_ok=True)
    output = RAW / "300750_2025-03-25_1222897257.pdf"
    output.write_bytes(content)
    print(
        json.dumps(
            {
                "url": args.url,
                "pdf_bytes": len(content),
                "pages": len(reader.pages),
                "extracted_characters": len(text.strip()),
                "contains_stock_code": "300750" in text,
                "preview": text.strip()[:180],
                "saved_to": str(output.relative_to(RAW.parent.parent)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
