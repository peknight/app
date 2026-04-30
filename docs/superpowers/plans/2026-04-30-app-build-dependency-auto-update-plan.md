# app-build 依赖版本自动更新脚本 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建 Python 脚本，通过 `@versionCheck` 注释锚点定位 app-build 中的第三方应用版本定义，从官方 API 检索最新版本号并更新。

**Architecture:** 单文件 Python 脚本，纯标准库实现。按 API 类型分为 4 个更新函数（Adoptium、Node.js、GitHub Release、Mojang Manifest），共享通用的锚点解析和版本比较逻辑。

**Tech Stack:** Python 3, urllib, re, json, os, argparse

---

### Task 1: 脚本骨架与通用工具函数

**Files:**
- Create: `scripts/update-app-deps.py`

- [ ] **Step 1: 创建脚本骨架**

```python
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
    except Exception as e:
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
    for j in range(comment_idx - 1, max(0, comment_idx - 4), -1):
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
```

- [ ] **Step 2: 验证脚本可解析**

Run: `python3 -c "import py_compile; py_compile.compile('scripts/update-app-deps.py', doraise=True)"`
Expected: 无报错

---

### Task 2: Adoptium Temurin JDK 版本检查

**Files:**
- Modify: `scripts/update-app-deps.py`

- [ ] **Step 1: 添加 Adoptium 版本查询函数**

追加到脚本末尾 `main()` 之前：

```python
def _query_adoptium_latest() -> str | None:
    """查询 Adoptium Temurin 最新版本，返回 XX_YY 格式。

    先检查是否有更新的大版本，再获取对应小版本。
    """
    # 1. 获取所有可用大版本
    data = _fetch_json(API_ADOPTIUM_RELEASES)
    if data is None:
        return None
    available = data.get("available_releases", [])
    if not available:
        return None

    # 返回最大版本号
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
```

- [ ] **Step 2: 添加 Adoptium 更新函数**

```python
def update_adoptium(repo_root: Path, apply: bool) -> list[dict]:
    """更新 adoptium.temurin.jdk 的版本号和 URL。"""
    results = []
    filepath = repo_root / "app-build" / "shared" / "src" / "main" / "scala" / "com" / "peknight" / "app" / "build" / "package.scala"
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

        # 同时更新 url 行（引用了 version 变量，自动生效无需修改）
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
```

---

### Task 3: Node.js 版本检查

**Files:**
- Modify: `scripts/update-app-deps.py`

- [ ] **Step 1: 添加 Node.js 版本查询和更新函数**

```python
def _query_nodejs_latest() -> str | None:
    """查询 Node.js 最新 current 版本号。"""
    data = _fetch_json(API_NODEJS)
    if data is None or not isinstance(data, list) or len(data) == 0:
        return None
    # index.json 按时间倒序，取第一个 current 类型
    for entry in data:
        if entry.get("lts") or entry.get("version", "").startswith("v"):
            version = entry.get("version", "")
            if version.startswith("v"):
                return version[1:]
    return None


def update_nodejs(repo_root: Path, apply: bool) -> list[dict]:
    """更新 node 的版本号和 URL。"""
    results = []
    filepath = repo_root / "app-build" / "shared" / "src" / "main" / "scala" / "com" / "peknight" / "app" / "build" / "package.scala"
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

        # 更新 url 行（含 version 引用，更新 url 中的 version 占位符）
        url_info = _find_url_def_after_comment(lines, version_line_idx + 1)
        if url_info:
            url_line_idx, current_url_value = url_info
            # url 行中使用 version 变量构建，无需修改 URL 行本身
            # 但 directory 行需要更新
            dir_line = _find_directory_line_after_comment(lines, version_line_idx)
            if dir_line is not None:
                old_dir = lines[dir_line]
                new_dir = old_dir.replace(f'v{current_version}-', f'v{latest}-', 1)
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
```

- [ ] **Step 2: 添加 _find_directory_line_after_comment 辅助函数**

在 `_find_url_def_after_comment` 之后添加：

```python
def _find_directory_line_after_comment(lines: list[str], start: int) -> int | None:
    """从 start 行开始查找 val directory: Path = ...。"""
    for j in range(start, min(start + 5, len(lines))):
        if "val directory" in lines[j] and "Path" in lines[j]:
            return j
    return None
```

---

### Task 4: GitHub Release 版本检查（frp、xxl-job、apollo）

**Files:**
- Modify: `scripts/update-app-deps.py`

- [ ] **Step 1: 添加 GitHub Release 查询和通用更新函数**

```python
def _query_github_latest(owner: str, repo: str) -> str | None:
    """通过 GitHub API 查询最新 release tag_name。"""
    url = GITHUB_RELEASE.format(owner=owner, repo=repo)
    data = _fetch_json(url)
    if data is None:
        return None
    tag_name = data.get("tag_name", "")
    if not tag_name:
        return None
    # 去掉 v 前缀
    if tag_name.startswith("v"):
        return tag_name[1:]
    return tag_name


def update_github_release(repo_root: Path, apply: bool, owner: str, repo: str, display_name: str, skip_names: set[str] | None = None) -> list[dict]:
    """更新 GitHub Release 类型应用的版本号。

    Args:
        owner: GitHub 仓库所有者
        repo: GitHub 仓库名
        display_name: 显示名称
        skip_names: 需要跳过的 object 名称集合
    """
    results = []
    filepath = repo_root / "app-build" / "shared" / "src" / "main" / "scala" / "com" / "peknight" / "app" / "build" / "package.scala"
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    # 从 URL 锚点定位
    github_url = f"https://github.com/{owner}/{repo}/releases"
    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        url = url_match.group(1)
        if github_url not in url:
            i += 1
            continue

        object_name = _find_object_name_before_comment(lines, i)
        if not object_name:
            i += 1
            continue

        if skip_names and object_name in skip_names:
            i += 1
            continue

        if object_name in EXCLUDE_NAMES:
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
```

- [ ] **Step 2: 验证 frp、xxl-job、apollo 的锚点 URL 匹配逻辑**

当前 package.scala 中的锚点 URL 格式为 `// https://github.com/.../releases/`，需要确认 GitHub URL 能匹配。修改锚点搜索逻辑，将 `ANCHOR_RE` 匹配到的 URL 与 `github_url` 做包含判断时，支持 `//` 注释格式的 URL。

在当前 `update_github_release` 中，锚点 URL 是 `// https://github.com/fatedier/frp/releases/` 格式（双斜杠注释），而 ANCHOR_RE 匹配的是 `/** @versionCheck ... */` 格式。

查看实际源码：锚点在注释 `// https://github.com/...` 下方是 `val version: String = "x.y.z"`，**没有** `/** @versionCheck ... */` 格式的锚点。

需要先在 `package.scala` 中添加 `@versionCheck` 锚点。这应该在 Task 0 或单独步骤中完成。将此作为 Task 5 的前置步骤。

---

### Task 5: 为 package.scala 添加 @versionCheck 锚点

**Files:**
- Modify: `app-build/shared/src/main/scala/com/peknight/app/build/package.scala`

- [ ] **Step 1: 更新所有版本定义为 @versionCheck 格式**

将当前文件中的所有版本注释替换为统一的 `@versionCheck` 锚点格式：

```scala
package com.peknight.app

import com.peknight.build.gav
import fs2.io.file.Path
import org.http4s.Uri
import org.http4s.syntax.literals.uri

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

package object build:
  object adoptium:
    object temurin:
      /** @versionCheck https://api.adoptium.net/v3/info/available_releases */
      object jdk:
        object x64:
          object linux:
            val version: String = "26_35"
            val url: Uri = Uri.unsafeFromString(s"https://github.com/adoptium/temurin26-binaries/releases/download/jdk-${URLEncoder.encode(version.replace('_', '+'), StandardCharsets.UTF_8)}/OpenJDK26U-jdk_x64_linux_hotspot_$version.tar.gz")
          end linux
        end x64
      end jdk
    end temurin
  end adoptium
  object sbt:
    // @versionCheck https://repo.maven.apache.org/maven2/org/scala-sbt/sbt/
    val version: String = gav.sbtScala.version
    val url: Uri = Uri.unsafeFromString(s"https://github.com/sbt/sbt/releases/download/v$version/sbt-$version.tgz")
  end sbt
  object node:
    /** @versionCheck https://nodejs.org/dist/index.json */
    object linux:
      object x64:
        val version: String = "25.9.0"
        val directory: Path = Path(s"node-v$version-linux-x64")
        val url: Uri = Uri.unsafeFromString(s"https://nodejs.org/dist/v$version/$directory.tar.xz")
      end x64
    end linux
  end node
  object fatedier:
    /** @versionCheck https://api.github.com/repos/fatedier/frp/releases/latest */
    object frp:
      val version: String = "0.68.1"
      val url: Uri = Uri.unsafeFromString(s"https://github.com/fatedier/frp/releases/download/v$version/frp_${version}_linux_amd64.tar.gz")
    end frp
  end fatedier
  object xuxueli:
    /** @versionCheck https://api.github.com/repos/xuxueli/xxl-job/releases/latest */
    object `xxl-job`:
      val version: String = "3.4.0"
      val tablesXxlJobSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/xuxueli/xxl-job/refs/tags/$version/doc/db/tables_xxl_job.sql")
    end `xxl-job`
  end xuxueli
  object apolloconfig:
    /** @versionCheck https://api.github.com/repos/apolloconfig/apollo/releases/latest */
    object apollo:
      val version: String = "2.5.1"
      val apolloPortalDbSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/apolloconfig/apollo/refs/tags/v$version/scripts/sql/profiles/mysql-default/apolloportaldb.sql")
      val apolloConfigDbSql: Uri = Uri.unsafeFromString(s"https://raw.githubusercontent.com/apolloconfig/apollo/refs/tags/v$version/scripts/sql/profiles/mysql-default/apolloconfigdb.sql")
    end apollo
  end apolloconfig
  object mojang:
    /** @versionCheck https://launchermeta.mojang.com/mc/game/version_manifest.json */
    object minecraft:
      object java:
        val version: String = "26.1.2"
        val url: Uri = uri"https://piston-data.mojang.com/v1/objects/97ccd4c0ed3f81bbb7bfacddd1090b0c56f9bc51/server.jar"
      end java
      object bedrock:
        val version: String = "1.26.14.1"
        val url: Uri = Uri.unsafeFromString(s"https://www.minecraft.net/bedrockdedicatedserver/bin-linux/bedrock-server-$version.zip")
      end bedrock
    end minecraft
  end mojang
end build
```

注意变化：
- adoptium: `// https://github.com/adoptium/temurin26-binaries/releases/` → `/** @versionCheck https://api.adoptium.net/v3/info/available_releases */`
- node: `// https://nodejs.org/en/download/current` → `/** @versionCheck https://nodejs.org/dist/index.json */`
- frp: `// https://github.com/fatedier/frp/releases/` → `/** @versionCheck https://api.github.com/repos/fatedier/frp/releases/latest */`
- xxl-job: `// https://github.com/xuxueli/xxl-job/releases/` → `/** @versionCheck https://api.github.com/repos/xuxueli/xxl-job/releases/latest */`
- apollo: `// https://github.com/apolloconfig/apollo/releases/` → `/** @versionCheck https://api.github.com/repos/apolloconfig/apollo/releases/latest */`
- minecraft: 无注释 → `/** @versionCheck https://launchermeta.mojang.com/mc/game/version_manifest.json */`

- [ ] **Step 2: 提交**

```bash
git add app-build/shared/src/main/scala/com/peknight/app/build/package.scala
git commit -m "chore: add @versionCheck anchors to app-build package.scala"
```

---

### Task 6: Minecraft 版本检查（Java / Bedrock）

**Files:**
- Modify: `scripts/update-app-deps.py`

- [ ] **Step 1: 添加 Mojang 版本查询和更新函数**

```python
def _query_mojang_latest() -> tuple[str | None, str | None]:
    """查询 Minecraft 最新版本，返回 (java_version, java_url, bedrock_version)。"""
    data = _fetch_json(API_MOJANG_MANIFEST)
    if data is None:
        return None, None, None

    latest_release = data.get("latest", {}).get("release")
    if not latest_release:
        return None, None, None

    # 获取 Java 版详情
    versions = data.get("versions", [])
    java_url = None
    for v in versions:
        if v.get("id") == latest_release:
            detail = _fetch_json(v.get("url", ""))
            if detail:
                downloads = detail.get("downloads", {})
                server = downloads.get("server", {})
                java_url = server.get("url")
            break

    return latest_release, java_url, latest_release


def update_minecraft(repo_root: Path, apply: bool) -> list[dict]:
    """更新 Minecraft Java 和 Bedrock 的版本号和 URL。"""
    results = []
    filepath = repo_root / "app-build" / "shared" / "src" / "main" / "scala" / "com" / "peknight" / "app" / "build" / "package.scala"
    if not filepath.exists():
        return results

    content = filepath.read_text()
    lines = content.splitlines()
    modified = False

    # 定位锚点
    i = 0
    while i < len(lines):
        url_match = ANCHOR_RE.search(lines[i])
        if not url_match:
            i += 1
            continue

        url = url_match.group(1)
        if "launchermeta.mojang.com" not in url:
            i += 1
            continue

        # 查找 java 和 bedrock 的版本定义
        block_start = i
        # 向后搜索到 end mojang 或文件末尾
        j = block_start + 1
        while j < len(lines) and "end mojang" not in lines[j]:
            # Java version
            if 'val version: String = "' in lines[j] and "java" in "".join(lines[max(0,j-5):j]).lower():
                java_ver_match = VAL_VERSION_RE.search(lines[j])
                if java_ver_match:
                    java_ver_line = j
                    java_current = java_ver_match.group(2)
            # Bedrock version
            if 'val version: String = "' in lines[j] and "bedrock" in "".join(lines[max(0,j-5):j]).lower():
                bedrock_ver_match = VAL_VERSION_RE.search(lines[j])
                if bedrock_ver_match:
                    bedrock_ver_line = j
                    bedrock_current = bedrock_ver_match.group(2)
            j += 1

        # 查询最新版本
        latest_ver, java_url, _ = _query_mojang_latest()
        if latest_ver is None:
            results.append({"name": "mojang.minecraft", "status": "error", "reason": "查询失败"})
            i += 1
            continue

        # 更新 Java 版
        if java_ver_line and java_current and _is_version_newer(java_current, latest_ver):
            old_line = lines[java_ver_line]
            lines[java_ver_line] = old_line.replace(java_current, latest_ver, 1)

            # 更新 Java URL
            for k in range(java_ver_line + 1, min(java_ver_line + 3, len(lines))):
                if "val url" in lines[k] and "java" not in lines[k]:
                    if java_url:
                        # 提取新 URL 中的 hash 部分
                        old_url_match = re.search(r'(uri"https?://[^\s]*/objects/)([a-f0-9]+)(/server\.jar")', lines[k])
                        if old_url_match:
                            new_hash = java_url.split("/")[-2]  # hash 在 URL 倒数第二段
                            lines[k] = lines[k].replace(old_url_match.group(2), new_hash, 1)
                            modified = True

            modified = True
            results.append({
                "name": "mojang.minecraft.java",
                "status": "updated",
                "old": java_current,
                "new": latest_ver,
            })
        else:
            results.append({"name": "mojang.minecraft.java", "status": "skipped", "reason": f"已是最新 ({java_current})"})

        # 更新 Bedrock 版
        if bedrock_ver_line and bedrock_current and _is_version_newer(bedrock_current, latest_ver):
            old_line = lines[bedrock_ver_line]
            lines[bedrock_ver_line] = old_line.replace(bedrock_current, latest_ver, 1)
            modified = True
            results.append({
                "name": "mojang.minecraft.bedrock",
                "status": "updated",
                "old": bedrock_current,
                "new": latest_ver,
            })
        else:
            results.append({"name": "mojang.minecraft.bedrock", "status": "skipped", "reason": f"已是最新 ({bedrock_current})"})

        break

    if modified and apply:
        filepath.write_text("\n".join(lines) + "\n")

    return results
```

---

### Task 7: 打印结果与 CLI 入口

**Files:**
- Modify: `scripts/update-app-deps.py`

- [ ] **Step 1: 添加打印结果函数和 main 函数**

```python
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
```

- [ ] **Step 2: dry-run 测试**

```bash
python3 scripts/update-app-deps.py
```

Expected: 输出 dry-run header，列出各应用状态

- [ ] **Step 3: 提交**

```bash
git add scripts/update-app-deps.py
git commit -m "feat: add app-build dependency version auto-update script"
```

---

### Task 8: 创建 SKILL.md

**Files:**
- Create: `.claude/skills/update-app-deps/SKILL.md`

- [ ] **Step 1: 创建 SKILL.md**

```markdown
---
name: update-app-deps
description: |
  自动更新 app-build 模块中第三方应用的最新版本号。
  触发词："更新 app 依赖版本"、"update app deps"。
  流程：直接 --apply 执行 → 展示结果 → 自动 git commit。
---

# app-build 依赖版本自动更新

## 触发条件

用户说 "更新一下 app 依赖版本"、"update app deps" 等类似表述。

## 执行流程

### Step 1: 执行更新

```bash
python3 scripts/update-app-deps.py --apply
```

### Step 2: 展示结果

向用户展示更新结果，列出已更新/跳过/错误的应用。

### Step 3: 提交变更

如果有更新的依赖：

```bash
git add app-build/shared/src/main/scala/com/peknight/app/build/package.scala
git commit -m "$(cat <<'EOF'
chore: bump app dependency versions
EOF
)"
```

## 注意事项

- 脚本位于 `scripts/update-app-deps.py`，使用纯 Python 标准库，零外部依赖
- 更新范围：`app-build/package.scala`
- 不要手动修改版本号，统一通过脚本执行
- GitHub API 可通过环境变量 `GITHUB_TOKEN` 传入认证 token 提升限频
```

- [ ] **Step 2: 提交**

```bash
git add .claude/skills/update-app-deps/SKILL.md
git commit -m "chore: add update-app-deps skill"
```

---

## Self-Review

### 1. Spec coverage

| 设计需求 | 对应 Task |
|---------|----------|
| `@versionCheck` 锚点格式 | Task 5 |
| Adoptium Temurin JDK 大版本+小版本检查 | Task 2 |
| Node.js 版本检查 | Task 3 |
| GitHub Release（frp/xxl-job/apollo） | Task 4 |
| Minecraft Java/Bedrock | Task 6 |
| CLI 接口（dry-run/--apply/--skip） | Task 7 |
| 输出格式 | Task 7 |
| 纯 Python 标准库 | 全局 |
| GITHUB_TOKEN 支持 | Task 1 (_fetch_json) |
| sbt 跳过 | Task 1 (EXCLUDE_NAMES) |

### 2. Placeholder scan

搜索 "TBD", "TODO", "implement later", "add appropriate" — 无发现。

### 3. Type consistency

- `_fetch_json` 返回 `dict | list | None` — 全局一致
- `_parse_version_tuple` 返回 `tuple` — 全局一致
- `_is_version_newer` 接受两个 `str` — 全局一致
- 所有 update 函数返回 `list[dict]` — 全局一致

### Issues found and fixed

1. **Task 4 锚点匹配问题**：当前 package.scala 使用 `//` 注释而非 `@versionCheck` 格式。已在 Task 5 中作为前置步骤统一替换。
2. **Task 3 Node.js directory 行更新**：添加了 `_find_directory_line_after_comment` 辅助函数来同步更新 directory 路径中的版本号。
3. **Task 6 Minecraft Java URL 更新**：Java 版 URL 为固定 hash 格式，需要从 Mojang 版本详情 JSON 中提取新 hash。代码中通过提取 URL 倒数第二段的 hash 来更新。
