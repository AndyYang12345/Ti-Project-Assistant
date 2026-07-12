---
name: release
description: >-
  自动打 tag 并推送，触发 GitHub Actions 构建 whl 并发布到 PyPI。
  当用户提到发布、release、发版、推送新版本、bump version、打 tag 时自动调用。
  触发词示例：「发布新版本」「release」「发版」「bump」「推送 0.4.0」。
---

# 发布 Skill — 一键 tag 推送 PyPI

## 工作流原理

```
git tag vX.Y.Z → git push → GitHub Actions 自动构建 → PyPI 发布
                              ├── build: hatch-vcs 读取 tag → python -m build
                              └── publish: twine 推送 (仅 tag 触发 + environment:release)
```

版本号由 `git tag` 唯一驱动，`hatch-vcs` 构建时自动提取。**不需要修改任何源文件中的版本号。**

## 发布流程

### Step 1: 确认状态

```bash
git tag --list 'v*' | sort -V | tail -3   # 最新 tag
git status --short                          # 工作区是否干净
git branch --show-current                   # 必须在 main
git log origin/main..HEAD --oneline         # 未推送的提交
```

### Step 2: 确定版本号

根据用户意图计算下一版本：

| 用户说 | 类型 | 计算方式 |
|--------|------|---------|
| "patch"、"修bug"、"小修复" | patch | 末位 +1 |
| "minor"、"新功能"、"feature" | minor | 中间位 +1，末位归零 |
| "major"、"大版本"、"breaking" | major | 首位 +1，其余归零 |
| "发布 X.Y.Z" | 自定义 | 直接使用指定版本 |

### Step 3: 提交 + 打 tag + 推送

```bash
# 如有未暂存更改，先提交
git add -A
git commit -m "<描述变更>"

# 推送 main（确保 commit 在远程）
git push origin main

# 打 tag 并推送（推送 tag 即触发 CI）
git tag v{version}
git push origin v{version}
```

### Step 4: 确认触发

推送后告知用户：
- **工作流**: https://github.com/AndyYang12345/Ti-Project-Assistant/actions/workflows/publish.yml
- **PyPI**: https://pypi.org/project/ti-project-assistant/

## 关键约束

1. **不修改源文件版本号** — `pyproject.toml` 和 `__init__.py` 是动态版本
2. **tag 必须以 `v` 开头** — GitHub Actions 匹配 `v*` 触发
3. **不添加 Co-Authored-By** — commit 不含 Claude 署名
4. **PyPI 环境名 `release`** — 需与 Trusted Publisher 配置一致
5. **GitHub 仓库 `release` 环境** — Settings → Environments 已配置

## 关键文件

| 文件 | 作用 |
|------|------|
| `.github/workflows/publish.yml` | CI/CD 构建发布工作流 |
| `pyproject.toml` | hatch-vcs 动态版本 + post-release scheme |
| `src/ti_project_assistant/__init__.py` | 运行时版本解析 |
| `src/ti_project_assistant/cli.py` | `--version` / `-V` 参数 |
