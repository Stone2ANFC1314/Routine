# -*- coding: utf-8 -*-
"""给 GitHub 仓库建 Release 并上传附件。

用 token 调 REST API。token 从 .ripple_github_token 读，不写在代码里。
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOKEN_FILE = Path.home() / ".ripple_github_token"
OWNER = "Stone2ANFC1314"


def token() -> str:
    return TOKEN_FILE.read_text(encoding="ascii").strip()


def api(method: str, url: str, data: dict | None = None, raw: bytes | None = None,
        content_type: str = "application/json") -> tuple[int, dict | str]:
    headers = {
        "Authorization": f"Bearer {token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ripple-release-uploader",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    elif raw is not None:
        body = raw
        headers["Content-Type"] = content_type

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return resp.status, (json.loads(text) if text.strip().startswith(("{", "[")) else text)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return exc.code, body_text


def create_release(repo: str, tag: str, name: str, body: str) -> dict | None:
    url = f"https://api.github.com/repos/{OWNER}/{repo}/releases"
    status, data = api("POST", url, {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False,
    })
    print(f"  创建 Release: HTTP {status}")
    if status not in (200, 201):
        print(f"    返回: {str(data)[:400]}")
        return None
    return data  # type: ignore[return-value]


def upload_asset(upload_url: str, file_path: Path) -> bool:
    """upload_url 形如 https://uploads.github.com/.../assets{?name,label}"""
    base = upload_url.split("{")[0]
    url = f"{base}?name={urllib.parse.quote(file_path.name)}"
    size_mb = file_path.stat().st_size / 1024 / 1024
    print(f"  上传 {file_path.name} ({size_mb:.1f} MB) …")
    status, data = api("POST", url, raw=file_path.read_bytes(),
                       content_type="application/zip")
    if status in (200, 201):
        print(f"    成功")
        return True
    print(f"    HTTP {status}: {str(data)[:300]}")
    return False


def main() -> int:
    repo = sys.argv[1] if len(sys.argv) > 1 else "Ripple"
    zip_path = Path(sys.argv[2])
    tag = sys.argv[3] if len(sys.argv) > 3 else "v1.0.0"
    title = sys.argv[4] if len(sys.argv) > 4 else "Ripple 1.0.0"
    notes = sys.argv[5] if len(sys.argv) > 5 else ""

    print(f"仓库: {OWNER}/{repo}")
    print(f"文件: {zip_path.name}")

    rel = create_release(repo, tag, title, notes)
    if rel is None:
        return 1

    upload = rel.get("upload_url", "")
    if not upload:
        print("  没拿到 upload_url")
        return 1

    ok = upload_asset(upload, zip_path)
    if ok:
        print(f"\n  下载页: {rel.get('html_url')}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
