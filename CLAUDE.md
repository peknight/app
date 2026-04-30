# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 模块概述

`app` 模块定义应用层抽象及第三方应用的版本依赖信息。

## 子模块结构

- **app-core** — 应用抽象，当前包含 `AppName` 值对象（跨 JVM/JS/Native 平台）
- **app-build** — 第三方应用版本依赖与下载 URL 定义（跨 JVM/JS 平台）

## 第三方应用版本依赖

所有非 Maven/Docker 的第三方应用版本统一在 `app-build` 的 `package.scala` 中管理。每个应用版本需包含：

1. 版本号的 `@versionCheck` 注释锚点（指向官方 releases 页面）
2. `version: String` 定义
3. `url: Uri` 或 `directory: Path` 等相关信息

```scala
object vendor:
  object product:
    // https://github.com/vendor/product/releases/
    val version: String = "x.y.z"
    val url: Uri = Uri.unsafeFromString(s"https://.../v$version/...")
```

### 已收录应用

| 应用 | 版本 | 用途 |
|------|------|------|
| Adoptium Temurin JDK | 26_35 | Java 运行时 |
| sbt | 同 gav.sbtScala.version | 构建工具 |
| Node.js | 25.9.0 | JS 运行时 |
| fatedier/frp | 0.68.1 | 内网穿透 |
| xuxueli/xxl-job | 3.4.0 | 分布式任务调度 |
| apolloconfig/apollo | 2.5.1 | 配置中心 |
| mojang/minecraft (Java) | 26.1.2 | 游戏服务器 |
| mojang/minecraft (Bedrock) | 1.26.14.1 | 游戏服务器 |

## 依赖划分原则

| 类型 | 维护位置 |
|------|----------|
| 非标准化第三方应用版本 | `app-build` |
| Maven GAV 依赖 | `build/build-gav` |
| Docker 镜像/版本 | `docker/docker-build` |

## 构建

```bash
sbt compile          # 编译所有子模块
sbt test             # 运行测试
sbt "appCoreJVM/test" # 运行单个子模块测试
```