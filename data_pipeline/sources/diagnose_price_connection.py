"""Compare the Eastmoney price endpoint with and without WSL proxy settings."""

import json
import os
from datetime import date, timedelta
from urllib.parse import urlsplit

import requests


URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")


def proxy_summary():
    result = {}
    for key in PROXY_KEYS:
        value = os.environ.get(key)
        if value:
            parsed = urlsplit(value if "://" in value else f"http://{value}")
            result[key] = {"set": True, "localhost": parsed.hostname in ("localhost", "127.0.0.1", "::1")}
    return result


def check(session, params):
    try:
        response = session.get(URL, params=params, timeout=12)
        result = {"status": response.status_code, "bytes": len(response.content)}
        try:
            payload = response.json()
            result["has_klines"] = bool((payload.get("data") or {}).get("klines"))
        except ValueError:
            result["json"] = False
        return result
    except requests.RequestException as error:
        return {"error": type(error).__name__}


def main():
    end = date.today()
    params = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
        "ut": "7eea3edcaed734bea9cbfc24409ed989",
        "klt": "101",
        "fqt": "1",
        "secid": "0.300750",
        "beg": (end - timedelta(days=120)).strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
    }
    with requests.Session() as default_session, requests.Session() as direct_session:
        direct_session.trust_env = False
        result = {
            "proxy_settings": proxy_summary(),
            "default_connection": check(default_session, params),
            "direct_connection": check(direct_session, params),
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
