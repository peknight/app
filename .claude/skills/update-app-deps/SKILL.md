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