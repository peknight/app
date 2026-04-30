# app-build 依赖版本自动更新脚本设计

## 项目概览

创建一个 Python 脚本，自动检索并更新 `app-build` 模块中所有第三方应用的最新版本号和下载 URL。参考 build 模块的 `update-deps.py` 实现风格，使用纯 Python 标准库，零外部依赖。

## 注释锚点格式

与 build 模块统一，使用 `/** @versionCheck <URL> */` 块注释：

```scala
/** @versionCheck https://api.adoptium.net/v3/info/available_releases */
val version: String = "26_35"
val url: Uri = Uri.unsafeFromString(s"...")
```

## 版本获取源

### Adoptium Temurin JDK

- **大版本检查**: `https://api.adoptium.net/v3/info/available_releases` → 返回 `[8, 11, 17, 21, 24, 25, 26, ...]`
- **小版本获取**: `https://api.adoptium.net/v3/assets/latest/{feature_version}/hotspot?architecture=x64&os=linux&image_type=jdk&project=jdk&vendor=adoptium` → 返回 `release_name`（如 `jdk-26+35`）

逻辑：
1. 从 `available_releases` 检查当前大版本 +1 是否存在
2. 存在 → 更新到最新大版本的最新小版本
3. 不存在 → 更新到当前大版本的最新小版本
4. `release_name` 格式为 `jdk-XX+YY`，转换为 `XX_YY` 格式

### Node.js

- **API**: `https://nodejs.org/dist/index.json` → 返回所有版本列表，按时间倒序
- 取第一条 `current` 类型的 `version` 字段（去掉 `v` 前缀）

### GitHub Releases（frp、xxl-job、apollo）

- **API 模板**: `https://api.github.com/repos/{owner}/{repo}/releases/latest`
- 返回 `tag_name` 字段，去掉 `v` 前缀即为版本号
- 支持通过环境变量 `GITHUB_TOKEN` 传入认证 token，提升限频到 5000 次/小时
- 需要同时更新 URL 的应用（frp、xxl-job 的 SQL、apollo 的 SQL）：用版本号重新拼接 URL

### Minecraft（Java / Bedrock）

- **API**: `https://launchermeta.mojang.com/mc/game/version_manifest.json`
- 返回 `latest.release` 为最新正式版版本号
- Java 版：请求版本详情 JSON 获取 `downloads.server.url`（固定 hash URL）
- Bedrock 版：用版本号拼接 URL（`bedrock-server-{version}.zip`）

## 解析策略

通过 `@versionCheck` 注释锚点定位，向上查找 `object` 名称用于显示和排除判断，向下查找版本号定义。

| 锚点 URL 类型 | 版本行格式 | URL 行格式 |
|--------------|-----------|-----------|
| Adoptium API | `val version: String = "XX_YY"` | `val url: Uri = ...`（含 version 引用）|
| Node.js API | `val version: String = "x.y.z"` | `val url: Uri = ...`（含 version 引用）|
| GitHub Release | `val version: String = "x.y.z"` | `val url: Uri = ...`（含 version 引用）|
| Mojang Manifest | `val version: String = "x.y.z"` | `val url: Uri = uri"..."`（固定 URL）|

## 排除列表

- **sbt**: 跳过不处理（引用 gav 模块版本）

## 命令行接口

```
python3 update-app-deps.py              # dry-run 模式，打印变更
python3 update-app-deps.py --apply      # 实际写入文件
python3 update-app-deps.py --skip frp   # 临时额外排除
```

## 输出格式

```
[已更新] adoptium.temurin.jdk: 26_35 → 27_10
[已更新] node: 25.9.0 → 25.10.0
[已更新] fatedier.frp: 0.68.1 → 0.69.0
[跳过]   sbt (跳过)
[跳过]   apolloconfig.apollo: 2.5.1 (已是最新)
[错误]   xxx (查询失败: HTTP 500)
```

## 技术实现

- 纯 Python 标准库（`urllib`、`re`、`json`），零外部依赖
- 脚本置于 `app/scripts/update-app-deps.py`
- 通过 `@versionCheck` 注释锚点直接定位版本号行
