"""Check the lowercase PDF fallback for CNINFO attachments."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from . import extract_announcement_texts


class FakeResponse:
    def __init__(self, status, content=b""):
        self.status_code = status
        self.headers = {"Content-Length": str(len(content))}
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def iter_content(self, chunk_size):
        yield self.content


class DownloadPdfTests(unittest.TestCase):
    def test_retries_lowercase_extension_after_404(self):
        url = "https://static.cninfo.com.cn/finalpage/2025-01-02/1222201503.PDF"
        pdf = b"%PDF-1.4\ntest"
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(extract_announcement_texts, "PDF_DIR", Path(temporary)):
                with patch.object(extract_announcement_texts.requests, "get", side_effect=[
                    FakeResponse(404), FakeResponse(200, pdf)
                ]) as get:
                    content, path, resolved_url = extract_announcement_texts.download_pdf(
                        "002594", "1222201503", url
                    )
            self.assertEqual(content, pdf)
            self.assertEqual(path.read_bytes(), pdf)
            self.assertEqual(resolved_url, url[:-4] + ".pdf")
            self.assertEqual([call.args[0] for call in get.call_args_list], [url, resolved_url])


if __name__ == "__main__":
    unittest.main()
