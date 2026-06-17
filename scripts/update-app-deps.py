#!/usr/bin/env python3
"""自动检索并更新 app-build 模块中第三方应用的最新版本号。

默认 dry-run 模式（仅打印变更），使用 --apply 参数实际写入。
"""

import argparse
import json
import os
import re
import urllib.request
from pathlib import Path

# === API 端点 ===

# Adoptium Temurin API
API_ADOPTIUM_RELEASES = "https://api.adoptium.net/v3/info/available_releases"
# Adoptium /latest/{feature}/hotspot 端点只返回原始 GA 版本，不包含后续季度更新。
# 改用 GitHub releases API 获取最新 release。
API_ADOPTIUM_RELEASES_GH = "https://api.github.com/repos/adoptium/temurin{feature_version}-binaries/releases?per_page=1"

# Node.js 官方 JSON
API_NODEJS = "https://nodejs.org/dist/index.json"

# GitHub Release API
GITHUB_RELEASE = "https://api.github.com/repos/{owner}/{repo}/releases/latest"

# Mojang version manifest
API_MOJANG_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

# === 正则 ===

# /** @versionCheck <URL> */ 块注释
ANCHOR_RE = re.compile(r"/\*\*\s*@versionCheck\s*(https?://[^\s]+)\s*\*/")

# /** @skipVersionCheck <URL> */ 块注释（URL 后可选附加说明）
SKIP_RE = re.compile(r"/\*\*\s*@skipVersionCheck\s+(https?://[^\s]+).*\*/")

# val version: String = "x.y.z"
VAL_VERSION_RE = re.compile(r'(val\s+version\s*:\s*String\s*=\s*")([^"]+)(")')

# val url: Uri = Uri.unsafeFromString(s"...") 或 val url: Uri = uri"..."
VAL_URL_RE = re.compile(r'(val\s+url\s*:\s*Uri\s*=\s*)(.+)')

# 目标文件路径
PACKAGE_PATH = Path("app-build") / "shared" / "src" / "main" / "scala" / "com" / "peknight" / "app" / "build" / "package.scala"


def _fetch_json(url: str, timeout: int = 15) -> dict | list | None:
    """请求 URL 并解析 JSON 响应。"""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "peknight-app-update-deps/1.0")
        # GitHub API token（可选）
        token = os.environ.get("GITHUB_TOKEN")
        if token and "api.github.com" in url:
            req.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _parse_version_tuple(version: str) -> tuple:
    """将版本号字符串解析为可比较的 tuple。

    支持 `1.26.14.1`、`0.68.1`、`25.9.0` 等格式。
    Adoptium 格式（如 26_35、26.0.1_8）使用 _is_adoptium_newer 比较。
    """
    parts = []
    for p in version.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            num = ""
            for c in p:
                if c.isdigit():
                    num += c
                else:
                    break
            parts.append(int(num) if num else 0)
    return tuple(parts)


def _is_adoptium_newer(current: str, candidate: str) -> bool:
    """比较 Adoptium 版本。

    格式：XX_YY（原始 GA，如 26_35）或 XX.Y.Z_YY（季度更新，如 26.0.1_8）。
    先比较主版本号，再比较小数版本号，最后比较 build 号。
    """
    def _normalize(v: str) -> tuple:
        if "_" not in v:
            return _parse_version_tuple(v) + (0,)
        main, build = v.rsplit("_", 1)
        parts = _parse_version_tuple(main)
        # 补齐到至少 (major, minor, security) 三位 + build
        while len(parts) < 3:
            parts = parts + (0,)
        return parts + (int(build),)

    return _normalize(candidate) > _normalize(current)


def _is_version_newer(current: str, candidate: str) -> bool:
    """判断 candidate 版本是否严格高于 current 版本。"""
    cur = _parse_version_tuple(current)
    cand = _parse_version_tuple(candidate)
    min_len = min(len(cur), len(cand))
    return cand[:min_len] > cur[:min_len]


def _find_object_name_before_comment(lines: list[str], comment_idx: int) -> str | None:
    """查找注释前最近的 object 名称（向上搜索）。"""
    for j in range(comment_idx - 1, max(0, comment_idx - 6), -1):
        m = re.search(r"object\s+(\w+)\s*[:{]", lines[j])
        if m:
            return m.group(1)
    return None


def _find_version_def_after_comment(lines: list[str], start: int) -> tuple[int, str] | None:
    """从 start 行开始查找 val version: String = "x.y.z"。"""
    for j in range(start, min(start + 5, len(lines))):
        m = VAL_VERSION_RE.search(lines[j])
        if m:
            return j, m.group(2)
    return None


def _find_url_def_after_comment(lines: list[str], start: int) -> tuple[int, str] | None:
    """从 start 行开始查找 val url: Uri = ...。"""
    for j in range(start, min(start + 5, len(lines))):
        m = VAL_URL_RE.search(lines[j])
        if m:
            return j, m.group(2)
    return None


def _find_directory_line(lines: list[str], start: int) -> int | None:
    """从 start 行开始查找 val directory: Path = ...。"""
    for j in range(start, min(start + 5, len(lines))):
        if "val directory" in lines[j] and "Path" in lines[j]:
            return j
    return None


def scan_skip_entries(repo_root: Path) -> list[dict]:
    """扫描所有 @skipVersionCheck 条目并报告为跳过。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()

    for i, line in enumerate(lines):
        skip_match = SKIP_RE.search(line)
        if skip_match:
            object_name = _find_object_name_before_comment(lines, i)
            if object_name:
                results.append({"name": object_name, "status": "skipped", "reason": "@skipVersionCheck"})

    return results


# === Adoptium Temurin JDK ===

def _query_adoptium_latest() -> str | None:
    """查询 Adoptium Temurin 最新版本，返回 XX_YY 或 XX.Y.Z_YY 格式。

    先检查是否有更新的大版本，再通过 GitHub releases API 获取最新季度更新。
    返回格式与下载文件名一致：26_35 或 26.0.1_8。
    """
    data = _fetch_json(API_ADOPTIUM_RELEASES)
    if data is None:
        return None
    available = data.get("available_releases", [])
    if not available:
        return None

    latest_major = max(available)
    return _query_adoptium_for_major(latest_major)


def _query_adoptium_for_major(feature_version: int) -> str | None:
    """通过 GitHub releases API 查询指定大版本的最新 release。

    返回格式与 package.scala 中的 val version 一致：
    - jdk-26+35 → 26_35（原始 GA）
    - jdk-26.0.1+8 → 26.0.1_8（季度更新）
    """
    url = API_ADOPTIUM_RELEASES_GH.format(feature_version=feature_version)
    data = _fetch_json(url, timeout=20)
    if data is None or not isinstance(data, list) or len(data) == 0:
        return None

    release = data[0]
    tag_name = release.get("tag_name", "")  # e.g. "jdk-26.0.1+8"
    # 从 release notes 或 aqavit 链接中推断版本号格式（文件名中的格式）
    # 例如：OpenJDK26U-jdk_x64_linux_hotspot_26.0.1_8.tar.gz
    assets = release.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        # 匹配 hotspot_XX_YY 或 hotspot_XX.Y.Z_YY 格式
        m = re.search(r"hotspot_([0-9.]+_\d+)\.tar\.gz", name)
        if m:
            return m.group(1)
    # fallback: 从 tag_name 解析
    return _adoptium_tag_to_version(tag_name)


def _adoptium_tag_to_version(tag: str) -> str | None:
    """将 Adoptium release tag 转换为版本字符串（fallback）。

    - jdk-26+35 → 26_35
    - jdk-26.0.1+8 → 26.0.1_8
    """
    m = re.match(r"jdk-([0-9.]+)\+(\d+)", tag)
    if not m:
        return None
    return f"{m.group(1)}_{m.group(2)}"


def update_adoptium(repo_root: Path, apply: bool) -> list[dict]:
    """更新 adoptium.temurin.jdk 的版本号。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        # 检查是否为 skip 标记
        if SKIP_RE.search(lines[i]):
            object_name = _find_object_name_before_comment(lines, i)
            if object_name:
                results.append({"name": object_name, "status": "skipped", "reason": "@skipVersionCheck"})
            i += 1
            continue

        url = url_match.group(1)
        if "api.adoptium.net" not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name:
            i += 1
            continue

        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        version_line_idx, current_version = version_info

        latest = _query_adoptium_latest()
        if latest is None or not _is_adoptium_newer(current_version, latest):
            results.append({"name": "adoptium.temurin.jdk", "status": "skipped", "reason": f"已是最新 ({current_version})"})
            i += 1
            continue

        old_line = lines[version_line_idx]
        lines[version_line_idx] = old_line.replace(current_version, latest, 1)
        modified = True

        results.append({
            "name": "adoptium.temurin.jdk",
            "status": "updated",
            "old": current_version,
            "new": latest,
        })
        i += 1

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results


# === Node.js ===

def _query_nodejs_latest() -> str | None:
    """查询 Node.js 最新 current 版本号。"""
    data = _fetch_json(API_NODEJS)
    if data is None or not isinstance(data, list) or len(data) == 0:
        return None
    # index.json 按时间倒序，取第一个条目
    for entry in data:
        version = entry.get("version", "")
        if version.startswith("v"):
            return version[1:]
    return None


def update_nodejs(repo_root: Path, apply: bool) -> list[dict]:
    """更新 node 的版本号和 URL。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        # 检查是否为 skip 标记
        if SKIP_RE.search(lines[i]):
            object_name = _find_object_name_before_comment(lines, i)
            if object_name:
                results.append({"name": object_name, "status": "skipped", "reason": "@skipVersionCheck"})
            i += 1
            continue

        url = url_match.group(1)
        if "nodejs.org/dist" not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name:
            i += 1
            continue

        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        version_line_idx, current_version = version_info

        latest = _query_nodejs_latest()
        if latest is None or not _is_version_newer(current_version, latest):
            results.append({"name": "node", "status": "skipped", "reason": f"已是最新 ({current_version})"})
            i += 1
            continue

        old_line = lines[version_line_idx]
        lines[version_line_idx] = old_line.replace(current_version, latest, 1)
        modified = True

        # 更新 directory 行中的版本号
        dir_line = _find_directory_line(lines, version_line_idx + 1)
        if dir_line is not None:
            old_dir = lines[dir_line]
            new_dir = old_dir.replace(f"v{current_version}-", f"v{latest}-", 1)
            if new_dir != old_dir:
                lines[dir_line] = new_dir

        results.append({
            "name": "node",
            "status": "updated",
            "old": current_version,
            "new": latest,
        })
        i += 1

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results


# === GitHub Release（frp、xxl-job、apollo）===

def _query_github_latest(owner: str, repo: str) -> str | None:
    """通过 GitHub API 查询最新 release tag_name。"""
    url = GITHUB_RELEASE.format(owner=owner, repo=repo)
    data = _fetch_json(url)
    if data is None:
        return None
    tag_name = data.get("tag_name", "")
    if not tag_name:
        return None
    if tag_name.startswith("v"):
        return tag_name[1:]
    return tag_name


def update_github_release(repo_root: Path, apply: bool, owner: str, repo: str, display_name: str) -> list[dict]:
    """更新 GitHub Release 类型应用的版本号。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    # 锚点 URL 为 api.github.com 格式
    github_anchor = f"api.github.com/repos/{owner}/{repo}/releases"

    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        # 检查是否为 skip 标记
        if SKIP_RE.search(lines[i]):
            object_name = _find_object_name_before_comment(lines, i)
            if object_name:
                results.append({"name": display_name, "status": "skipped", "reason": "@skipVersionCheck"})
            i += 1
            continue

        url = url_match.group(1)
        if github_anchor not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name:
            i += 1
            continue

        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        version_line_idx, current_version = version_info

        latest = _query_github_latest(owner, repo)
        if latest is None or not _is_version_newer(current_version, latest):
            results.append({"name": display_name, "status": "skipped", "reason": f"已是最新 ({current_version})"})
            i += 1
            continue

        old_line = lines[version_line_idx]
        lines[version_line_idx] = old_line.replace(current_version, latest, 1)
        modified = True

        results.append({
            "name": display_name,
            "status": "updated",
            "old": current_version,
            "new": latest,
        })
        i += 1

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results


# === Minecraft Java ===

def _query_mojang_latest() -> tuple[str | None, str | None]:
    """查询 Minecraft Java 最新版本，返回 (version_id, server_url)。"""
    data = _fetch_json(API_MOJANG_MANIFEST)
    if data is None:
        return None, None

    latest_release = data.get("latest", {}).get("release")
    if not latest_release:
        return None, None

    versions = data.get("versions", [])
    for v in versions:
        if v.get("id") == latest_release:
            detail = _fetch_json(v.get("url", ""), timeout=20)
            if detail:
                downloads = detail.get("downloads", {})
                server = downloads.get("server", {})
                return latest_release, server.get("url")
            break

    return latest_release, None


def update_minecraft_java(repo_root: Path, apply: bool) -> list[dict]:
    """更新 Minecraft Java 的版本号和 URL。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        # 检查是否为 skip 标记
        if SKIP_RE.search(lines[i]):
            results.append({"name": "mojang.minecraft.java", "status": "skipped", "reason": "@skipVersionCheck"})
            i += 1
            continue

        url = url_match.group(1)
        if "launchermeta.mojang.com" not in url:
            i += 1
            continue

        # 在锚点下方找 version 和 url
        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        ver_line_idx, current_version = version_info
        url_info = _find_url_def_after_comment(lines, ver_line_idx + 1)
        url_line_idx = url_info[0] if url_info else None

        latest_ver, latest_url = _query_mojang_latest()
        if latest_ver is None or not _is_version_newer(current_version, latest_ver):
            results.append({"name": "mojang.minecraft.java", "status": "skipped", "reason": f"已是最新 ({current_version})"})
            i += 1
            continue

        old_line = lines[ver_line_idx]
        lines[ver_line_idx] = old_line.replace(current_version, latest_ver, 1)
        modified = True

        # 更新 Java URL（固定 hash URL）
        if latest_url and url_line_idx is not None:
            old_url_match = re.search(r'/objects/([a-f0-9]+)/server\.jar"', lines[url_line_idx])
            new_hash_match = re.search(r'/objects/([a-f0-9]+)/server\.jar"', latest_url)
            if old_url_match and new_hash_match:
                lines[url_line_idx] = lines[url_line_idx].replace(old_url_match.group(1), new_hash_match.group(1), 1)

        results.append({
            "name": "mojang.minecraft.java",
            "status": "updated",
            "old": current_version,
            "new": latest_ver,
        })
        i += 1

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results


# === Minecraft Bedrock ===

def _query_mojang_bedrock() -> str | None:
    """查询 Minecraft Bedrock Dedicated Server 最新版本。

    Mojang manifest 仅包含 Java 版，Bedrock 版本通过社区维护的 JSON 获取。
    JSON 结构: {"release": {"1.26.14": {"linux": {"url": "...bedrock-server-1.26.14.1.zip"}}, ...}}
    从 Linux 下载 URL 中提取完整版本号（含最后一位修订号）。
    """
    url = "https://raw.githubusercontent.com/kittizz/bedrock-server-downloads/main/bedrock-server-downloads.json"
    data = _fetch_json(url)
    if data is None:
        return None
    release = data.get("release", {})
    if not release:
        return None
    version_keys = list(release.keys())
    version_keys.sort(key=_parse_version_tuple, reverse=True)
    latest_key = version_keys[0]
    linux_url = release[latest_key].get("linux", {}).get("url", "")
    m = re.search(r"bedrock-server-([0-9.]+)\.zip", linux_url)
    if m:
        return m.group(1)
    return latest_key


def update_minecraft_bedrock(repo_root: Path, apply: bool) -> list[dict]:
    """更新 Minecraft Bedrock 的版本号。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        # 检查是否为 skip 标记
        if SKIP_RE.search(lines[i]):
            results.append({"name": "mojang.minecraft.bedrock", "status": "skipped", "reason": "@skipVersionCheck"})
            i += 1
            continue

        url = url_match.group(1)
        if "bedrock-server-downloads" not in url:
            i += 1
            continue

        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        ver_line_idx, current_version = version_info

        latest = _query_mojang_bedrock()
        if latest is None or not _is_version_newer(current_version, latest):
            results.append({"name": "mojang.minecraft.bedrock", "status": "skipped", "reason": f"已是最新 ({current_version})"})
            i += 1
            continue

        old_line = lines[ver_line_idx]
        lines[ver_line_idx] = old_line.replace(current_version, latest, 1)
        modified = True

        results.append({
            "name": "mojang.minecraft.bedrock",
            "status": "updated",
            "old": current_version,
            "new": latest,
        })
        i += 1

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results


# === 结果打印 ===

def print_results(results):
    """打印更新结果汇总。"""
    print()
    print("=" * 60)
    for r in results:
        if r["status"] == "updated":
            print(f"[已更新] {r['name']}: {r['old']} → {r['new']}")
        elif r["status"] == "skipped":
            print(f"[跳过]   {r['name']} ({r['reason']})")
        elif r["status"] == "error":
            print(f"[错误]   {r['name']} ({r['reason']})")
    print("=" * 60)
    updated = sum(1 for r in results if r["status"] == "updated")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")
    print(f"已更新: {updated}  跳过: {skipped}  错误: {errors}")
    print("=" * 60)


# === CLI 入口 ===

def main():
    parser = argparse.ArgumentParser(description="自动更新 app-build 模块第三方应用版本号")
    parser.add_argument("--apply", action="store_true", help="实际写入文件（默认仅 dry-run）")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    if not args.apply:
        print("DRY-RUN 模式 - 不会修改任何文件")
    print("=" * 60)
    print()

    results = []
    results += scan_skip_entries(repo_root)
    results += update_adoptium(repo_root, args.apply)
    results += update_nodejs(repo_root, args.apply)
    results += update_github_release(repo_root, args.apply, "fatedier", "frp", "fatedier.frp")
    results += update_github_release(repo_root, args.apply, "xuxueli", "xxl-job", "xuxueli.xxl-job")
    results += update_github_release(repo_root, args.apply, "apolloconfig", "apollo", "apolloconfig.apollo")
    results += update_minecraft_java(repo_root, args.apply)
    results += update_minecraft_bedrock(repo_root, args.apply)

    print_results(results)


if __name__ == "__main__":
    main()
