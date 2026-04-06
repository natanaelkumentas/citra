# services/supabase_service.py — Semua HTTP call ke Supabase
# Dikumpulkan dari ImageAnalysisWindow dan AnalisisWarnaWindow.
# Tidak ada import tkinter di file ini.

import json
import urllib.request
import urllib.parse
import urllib.error

from core.config import SUPABASE_URL, SUPABASE_ANON_KEY


def _make_headers(prefer_return: bool = False) -> dict:
    """Buat header standar untuk request ke Supabase API."""
    headers = {
        "apikey":        SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type":  "application/json",
    }
    if prefer_return:
        headers["Prefer"] = "return=representation"
    return headers


def insert_record(table: str, data: dict, prefer_return: bool = True) -> list | None:
    """
    Insert satu record ke tabel Supabase.
    Return list response dari server, atau None jika gagal.

    Logika diambil dari ImageAnalysisWindow.supabase_request("POST", ...).
    """
    url     = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = _make_headers(prefer_return=prefer_return)
    payload = json.dumps(data).encode("utf-8")
    req     = urllib.request.Request(url=url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw.strip():
                return []
            return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Supabase insert error: {e}")


def fetch_records(table: str, select: str = "*", order: str = "created_at.desc",
                  limit: int = 50) -> list[dict]:
    """
    Ambil records dari tabel Supabase.
    Return list of dict.

    Logika diambil dari ImageAnalysisWindow.supabase_request("GET", ...).
    """
    query  = urllib.parse.urlencode({"select": select, "order": order, "limit": limit})
    url    = f"{SUPABASE_URL}/rest/v1/{table}?{query}"
    headers = _make_headers()
    req    = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            if not raw.strip():
                return []
            return json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"Supabase fetch error: {e}")


def delete_record(table: str, filter_query: str) -> None:
    """
    Hapus record dari tabel Supabase berdasarkan filter query.
    Contoh filter_query: "id=eq.42"
    """
    url     = f"{SUPABASE_URL}/rest/v1/{table}?{filter_query}"
    headers = _make_headers()
    req     = urllib.request.Request(url=url, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except Exception as e:
        raise RuntimeError(f"Supabase delete error: {e}")
