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
API_ADOPTIUM_LATEST = "https://api.adoptium.net/v3/assets/latest/{feature_version}/hotspot?architecture=x64&os=linux&image_type=jdk&project=jdk&vendor=adoptium"

# Node.js 官方 JSON
API_NODEJS = "https://nodejs.org/dist/index.json"

# GitHub Release API
GITHUB_RELEASE = "https://api.github.com/repos/{owner}/{repo}/releases/latest"

# Mojang version manifest
API_MOJANG_MANIFEST = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

# === 正则 ===

# /** @versionCheck <URL> */ 块注释
ANCHOR_RE = re.compile(r"/\*\*\s*@versionCheck\s*(https?://[^\s]+)\s*\*/")

# val version: String = "x.y.z"
VAL_VERSION_RE = re.compile(r'(val\s+version\s*:\s*String\s*=\s*")([^"]+)(")')

# val url: Uri = Uri.unsafeFromString(s"...") 或 val url: Uri = uri"..."
VAL_URL_RE = re.compile(r'(val\s+url\s*:\s*Uri\s*=\s*)(.+)')

# 排除列表
EXCLUDE_NAMES = {"sbt"}

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
    """将版本号字符串解析为可比较的 tuple。"""
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


# === Adoptium Temurin JDK ===

def _query_adoptium_latest() -> str | None:
    """查询 Adoptium Temurin 最新版本，返回 XX_YY 格式。

    先检查是否有更新的大版本，再获取对应小版本。
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
    """查询指定大版本的最新小版本，返回 XX_YY 格式。"""
    url = API_ADOPTIUM_LATEST.format(feature_version=feature_version)
    data = _fetch_json(url, timeout=20)
    if data is None or not isinstance(data, list) or len(data) == 0:
        return None

    release = data[0]
    release_name = release.get("release_name", "")  # e.g. "jdk-26+35"
    m = re.match(r"jdk-(\d+)\+(\d+)", release_name)
    if not m:
        return None
    major = int(m.group(1))
    patch = int(m.group(2))
    return f"{major}_{patch}"


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

        url = url_match.group(1)
        if "api.adoptium.net" not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name or object_name in EXCLUDE_NAMES:
            i += 1
            continue

        version_info = _find_version_def_after_comment(lines, i + 1)
        if not version_info:
            i += 1
            continue

        version_line_idx, current_version = version_info

        latest = _query_adoptium_latest()
        if latest is None or not _is_version_newer(current_version, latest):
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

        url = url_match.group(1)
        if "nodejs.org/dist" not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name or object_name in EXCLUDE_NAMES:
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

        url = url_match.group(1)
        if github_anchor not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name or object_name in EXCLUDE_NAMES:
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


# === Minecraft（Java / Bedrock）===

def _query_mojang_latest() -> tuple[str | None, str | None]:
    """查询 Minecraft Java 最新版本，返回 (version_id, server_url)。"""
    data = _fetch_json(API_MOJANG_MANIFEST)
    if data is None:
        return None, None

    latest_release = data.get("latest", {}).get("release")
    if not latest_release:
        return None, None

    # 获取 Java 版详情
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
    # 取版本号最大的版本
    version_keys = list(release.keys())
    version_keys.sort(key=_parse_version_tuple, reverse=True)
    latest_key = version_keys[0]
    # 从 URL 中提取完整版本号：bedrock-server-X.Y.Z.W.zip
    linux_url = release[latest_key].get("linux", {}).get("url", "")
    m = re.search(r"bedrock-server-([0-9.]+)\.zip", linux_url)
    if m:
        return m.group(1)
    return latest_key


def update_minecraft(repo_root: Path, apply: bool) -> list[dict]:
    """更新 Minecraft Java 和 Bedrock 的版本号和 URL。"""
    results = []
    filepath = repo_root / PACKAGE_PATH
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    # 定位锚点
    mojang_idx = None
    for i, line in enumerate(lines):
        url_match = ANCHOR_RE.search(line)
        if url_match and "launchermeta.mojang.com" in url_match.group(1):
            mojang_idx = i
            break

    if mojang_idx is None:
        results.append({"name": "mojang.minecraft", "status": "error", "reason": "未找到锚点"})
        return results

    # 查找 java 和 bedrock 的版本定义
    java_ver_line = None
    java_current = None
    java_url_line = None
    bedrock_ver_line = None
    bedrock_current = None

    j = mojang_idx + 1
    while j < len(lines) and "end mojang" not in lines[j]:
        if "object java" in lines[j]:
            # 在 java object 块内查找 version 和 url
            for k in range(j + 1, min(j + 6, len(lines))):
                if "end java" in lines[k]:
                    break
                vm = VAL_VERSION_RE.search(lines[k])
                if vm and java_ver_line is None:
                    java_ver_line = k
                    java_current = vm.group(2)
                um = VAL_URL_RE.search(lines[k])
                if um and java_url_line is None:
                    java_url_line = k
        if "object bedrock" in lines[j]:
            for k in range(j + 1, min(j + 6, len(lines))):
                if "end bedrock" in lines[k]:
                    break
                vm = VAL_VERSION_RE.search(lines[k])
                if vm and bedrock_ver_line is None:
                    bedrock_ver_line = k
                    bedrock_current = vm.group(2)
        j += 1

    # 查询最新版本
    latest_java_ver, latest_java_url = _query_mojang_latest()
    latest_bedrock = _query_mojang_bedrock()

    # 更新 Java 版
    if java_ver_line and java_current and latest_java_ver:
        if _is_version_newer(java_current, latest_java_ver):
            old_line = lines[java_ver_line]
            lines[java_ver_line] = old_line.replace(java_current, latest_java_ver, 1)

            # 更新 Java URL（固定 hash URL）
            if latest_java_url and java_url_line is not None:
                old_url_match = re.search(r'/objects/([a-f0-9]+)/server\.jar"', lines[java_url_line])
                if old_url_match:
                    new_hash_match = re.search(r'/objects/([a-f0-9]+)/server\.jar"', latest_java_url)
                    if new_hash_match:
                        old_hash = old_url_match.group(1)
                        new_hash = new_hash_match.group(1)
                        lines[java_url_line] = lines[java_url_line].replace(old_hash, new_hash, 1)
                        modified = True

            modified = True
            results.append({
                "name": "mojang.minecraft.java",
                "status": "updated",
                "old": java_current,
                "new": latest_java_ver,
            })
        else:
            results.append({"name": "mojang.minecraft.java", "status": "skipped", "reason": f"已是最新 ({java_current})"})
    else:
        results.append({"name": "mojang.minecraft.java", "status": "error", "reason": "未找到版本信息"})

    # 更新 Bedrock 版
    if bedrock_ver_line and bedrock_current and latest_bedrock:
        if _is_version_newer(bedrock_current, latest_bedrock):
            old_line = lines[bedrock_ver_line]
            lines[bedrock_ver_line] = old_line.replace(bedrock_current, latest_bedrock, 1)
            modified = True
            results.append({
                "name": "mojang.minecraft.bedrock",
                "status": "updated",
                "old": bedrock_current,
                "new": latest_bedrock,
            })
        else:
            results.append({"name": "mojang.minecraft.bedrock", "status": "skipped", "reason": f"已是最新 ({bedrock_current})"})
    else:
        results.append({"name": "mojang.minecraft.bedrock", "status": "error", "reason": "未找到版本信息"})

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
    parser.add_argument("--skip", nargs="*", default=[], metavar="NAME",
                        help="临时跳过指定依赖的更新（object 名称）")
    args = parser.parse_args()

    EXCLUDE_NAMES.update(args.skip)

    repo_root = Path(__file__).resolve().parent.parent

    print("=" * 60)
    if not args.apply:
        print("DRY-RUN 模式 - 不会修改任何文件")
    print("=" * 60)
    print()

    results = []
    results += update_adoptium(repo_root, args.apply)
    results += update_nodejs(repo_root, args.apply)
    results += update_github_release(repo_root, args.apply, "fatedier", "frp", "fatedier.frp")
    results += update_github_release(repo_root, args.apply, "xuxueli", "xxl-job", "xuxueli.xxl-job")
    results += update_github_release(repo_root, args.apply, "apolloconfig", "apollo", "apolloconfig.apollo")
    results += update_minecraft(repo_root, args.apply)

    print_results(results)


if __name__ == "__main__":
    main()
