# GitHub 发布与 Codex 一行安装

仓库为 [Cuinings/story-skill](https://github.com/Cuinings/story-skill)，默认分支为 `main`，技能源码在 `.agents/skills/story-codex`。不需要重排目录；`SKILL.md`、`scripts/`、`references/`、`agents/` 和 `LICENSE` 必须一起提交。只有源码推送到远端后，安装者才能获得新版本。

## 用户：在 Codex 对话框安装

发送这一行，由 Codex 的内置 skill-installer 完成下载和安装：

```text
$skill-installer https://github.com/Cuinings/story-skill/tree/main/.agents/skills/story-codex
```

安装后下一条消息即可点名使用；未显示时重启 Codex。需要本机有 Python 3.10+，运行时没有额外 Python 包或 API Key 要求。这不包含 Codex 本身的账号和使用额度。[OpenAI 官方说明](https://learn.chatgpt.com/zh-Hans/docs/build-skills)

```text
$story-codex 在 D:\小说\新书 创建中文长篇项目，计划300万字，先确定题材、创作约定、分卷规划和前三章细纲，不要写正文。
```

想安装固定版本，先确认维护者已经发布对应 tag。例如 **v0.3.0 tag 推送成功后**：

```text
$skill-installer https://github.com/Cuinings/story-skill/tree/v0.3.0/.agents/skills/story-codex
```

main 只代表安装当时的代码，不会自动更新。已存在同名技能时，官方安装器会拒绝覆盖；先让 Codex 确认实际安装路径、保留旧版及本地修改，再安装新版。不要把官方安装的目录交给本项目的 `install.py --update`：两者的安装清单不同。

只希望一个小说项目使用本技能，可以让 Codex 执行同一安装器并明确目标：

```text
$skill-installer 从 https://github.com/Cuinings/story-skill/tree/main/.agents/skills/story-codex 安装到 D:\小说\我的项目\.agents\skills，仅供这个项目使用。
```

安装器的 `--dest` 指向 **skills 父目录**，它会在其中创建 `story-codex`。如果本机同时保留项目和用户范围的同名技能，Codex 可能显示两份；选定实际要使用的一份，不将其当成自动合并或自动升级。

## 维护者：发布当前代码

本工作区已经有 origin，无需重新创建仓库。以下命令在 PowerShell 中逐条执行；先检查每条结果，失败时停止处理。它们会提交并推送本地代码，本文档本身不会执行这些操作。

```powershell
Set-Location "D:\Developer\WorkSpace\story-skill"
git status --short
git remote -v
python -B -X utf8 scripts/package.py
git add .agents/skills/story-codex scripts tests docs README.md benchmarks .gitignore .gitattributes LICENSE requirements-dev.txt
git diff --cached --stat
git commit -m "Release Story Codex v0.3.0"
git push origin main
```

检查暂存内容确实包含新增的 `story_storage.py`、`story_search.py`、`story_world.py`、`story_history.py` 和 `references/long-form.md`。不能只推入口文件，否则远端版本缺少运行依赖。上面的路径选择不包含本地环境、数据库或新增小说正文。推送成功后，main 的一行安装入口即能取得这次版本，不必先创建 Release。

## 发布固定版本和下载包

在已推送、通过验证的提交上创建 tag：

```powershell
git tag -a v0.3.0 -m "Story Codex v0.3.0"
git push origin refs/tags/v0.3.0
```

若该 tag 已存在，先检查它指向哪个提交，不要强制移动已经分发的版本标签。

打开 [创建 GitHub Release](https://github.com/Cuinings/story-skill/releases/new)，选择 `v0.3.0`，填写标题和说明，上传本地 `dist/story-codex-0.3.0.zip`，再发布。`dist/` 已被 Git 忽略，普通 push 不会上传 ZIP；Release 附件和 GitHub 自动生成的整仓库 Source code ZIP 是不同文件。[GitHub 官方发布步骤](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)

可用下面的摘要作为这次 Release 说明，并以实际打包输出为准：

> Codex 专用中文小说技能 v0.3.0。新增分卷多线、人物认知、远期伏笔、规则与资源状态、中文索引和历史修订分支。提供显式旧库迁移与备份恢复。发布前本机 226 项测试通过，并完成百万／千万字合成容量验证。多线流程冷加载指令减少约 84%；不代表总账单降幅或长期文学质量证明。

上传前读取包的校验值，便于下载者核对：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath "dist/story-codex-0.3.0.zip"
```

## 安装和验收范围

普通用户只需要技能目录，不需要维护者的测试环境、benchmark、示例数据库或 dist。安装成功以后，在实际安装目录运行 `python -B -X utf8 scripts/story.py --help` 应能加载完整运行时；是否实际显示在技能列表还应在 Codex 中确认。

维护者的完整历史验证依赖本地保留的旧版 ZIP 和三个旧示例数据库；这些文件受 `.gitignore` 保护。新 clone 不含它们，不能直接将新 clone 的完整验证等同于发布机器的历史验收。`scripts/smoke.py` 和 `scripts/long_acceptance.py` 会自行创建临时工程，可用于新 clone 的 CLI 检查；完整迁移复验需先准备明确的旧版测试材料。技能安装不会迁移任何书库，旧书迁移仍按 [恢复指南](recovery.md) 在独立副本进行。

## 同步到 GitHub Packages

[Packages 页面](https://github.com/users/Cuinings/packages?repo_name=story-skill) 与 Release 附件是两个分发渠道。本项目使用 GitHub npm 注册表，包名为 `@cuinings/story-codex`，版本与 Release 的技能版本一致。包内为 `story-codex/` 完整技能目录及两份 npm 元数据文件；没有依赖、安装钩子或自动注册 Codex 的脚本。

[同步工作流](../.github/workflows/packages.yml) 在正式 Release 发布时执行；也可以打开 [Actions](https://github.com/Cuinings/story-skill/actions/workflows/packages.yml)，选择 **Run workflow**，填写已发布的 tag，例如 `v0.3.0`，补同步历史版本。工作流需存在于被触发的代码版本中；较早的 tag 使用 main 分支的手动运行入口。

同步只读取对应 Release 的 `story-codex-<版本>.zip` 和 `.zip.sha256`，不会把当前 main 的其他改动装进旧版本包。使用仓库 `GITHUB_TOKEN`，权限限定为 `contents: read` 和 `packages: write`，不用创建或提交个人访问令牌。发布完成后，从 npm 注册表重新下载 tarball，检查 SHA-512、包身份和每个技能文件，并在临时工程执行版本、帮助、初始化和状态检查。回执保留为 Actions artifact。

重复同步时先核对现有版本。内容一致则记为已同步，内容不同则停止，不删除或覆盖该版本。修改了技能文件清单时，也须更新构建器的显式白名单，避免新文件在分发中缺失。

只在本地构建和验证，不发布：

```powershell
python -B -X utf8 scripts/sync_packages.py --tag v0.3.0 --prepare-only
```

已经按 GitHub 的 npm 说明完成认证后，可以下载内容包：

```powershell
npm pack @cuinings/story-codex@0.3.0 --registry=https://npm.pkg.github.com
```

npm tarball 不是本项目 `install.py` 的托管安装。包的可见性与仓库可见性分别管理；以 Packages 页面实际设置为准。GitHub npm 即使公开也需要认证下载，普通 Codex 用户仍使用 GitHub 技能路径安装。[GitHub npm 官方说明](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry)
