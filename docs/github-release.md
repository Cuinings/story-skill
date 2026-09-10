# 安装、升级与 GitHub 发布

仓库为 [NingCui29/story-skill](https://github.com/NingCui29/story-skill)。**v0.4.0 已于 2026-09-10 正式发布，包含 7 个技能入口、中文场景指导与运行时修复，安装默认固定到 `v0.4.0` 标签。** 发布附件、远端检查与 npm 同步分别验证，结果见下表。历史 v0.3.0 保留旧单入口目录和固定链接。

2026-09-10 本地验证记录：311 项测试、12 项整包检查通过，ZIP/npm 与源码的 31 个载荷文件一致，项目安装已核对。该记录不代替远端 CI、Release 下载或注册表验证。[完整修复与回执](全仓审查与优化.md) · [文档导航](README.md)

## v0.4.0 发布验证记录

固定标签指向提交 `c1b3c3377573610a191e165ceb6866ae35afe5a8`，不随后续文档更新移动。以下结果按发布环节分别记录：

| 环节 | 实际结果与证据 |
|---|---|
| GitHub Release | [v0.4.0](https://github.com/NingCui29/story-skill/releases/tag/v0.4.0) 于 2026-09-10 11:04:24（北京时间）发布，包含套件 ZIP 与 SHA-256 校验文件。[发布回执](../benchmarks/results/v0.4.0/release/release.json) |
| 发布提交的远端 CI | [运行 34431400166](https://github.com/NingCui29/story-skill/actions/runs/34431400166) 全步骤成功。Windows/Python 3.12：311 项通过、零跳过；Linux/Python 3.10：305 项通过、6 项 Windows 专用测试跳过。两端均完成打包、CLI 冒烟、中文稿件重放和多线历史修订演练。[CI 回执](../benchmarks/results/v0.4.0/release/ci.json) |
| 公共固定标签安装 | 用本机官方安装器从 `v0.4.0` 下载到隔离临时目录，7 个技能的 31 个文件与 Release ZIP、源码逐字节一致；安装后 `--version`、`--help`、`init`、`status` 全部成功。[安装回执](../benchmarks/results/v0.4.0/release/remote-install.json) |
| GitHub Packages | [运行 34431905475](https://github.com/NingCui29/story-skill/actions/runs/34431905475) 成功发布 `@ningcui29/story-codex@0.4.0`，回下载 tarball 的 31 个技能文件与 Release 一致，4 项运行时检查通过。包可见性为 public，关联当前仓库；[未登录可见的包页面](https://github.com/NingCui29/story-skill/pkgs/npm/story-codex) 显示 0.4.0 Latest。[原始回执](../benchmarks/results/v0.4.0/release/packages.json) · [下载后再次核对](../benchmarks/results/v0.4.0/release/package-check.json) |

Release ZIP 的 SHA-256 为 `087ad76fe32714ea776853cab579c3b6087ed092ef0857c55a76ae20aff7d54b`。固定标签安装只操作临时技能与临时书库，不修改用户安装或小说；它验证文件安装与运行时启动，不等于 Codex UI 自动发现或长程文学质量验证。

注册表回下载 tarball 的 SHA-256 为 `0cc37dcf98580b1ab7379ec7c54f23167b972e9e5d404679502fd975d982fa71`，与本地构建包逐字节一致；Actions 归档回执下载后也再次核对通过。[工作流与归档信息](../benchmarks/results/v0.4.0/release/packages-workflow.json)。公开包页面可浏览，GitHub npm 下载仍需要认证；npm 包本身不注册 Codex 技能。

首轮远端 Windows 检查曾因 5 个测试夹具没有规范化 TEMP 的 8.3 短路径而失败；Linux 当轮已通过。随后仅修正测试路径，将修改提交为上述发布提交，再重新运行两端 CI；没有修改技能载荷或生产脚本。[首轮失败回执](../benchmarks/results/v0.4.0/release/ci-first-failed.json) 保留，发布前的本地审查与文学评阅也不回写成远端结果。

## Codex 一行安装或升级

首次安装、补齐技能和旧版升级都使用同一行：

```text
$skill-installer 按 https://github.com/NingCui29/story-skill/blob/main/INSTALL.md 安装或升级 Story Codex
```

Codex 先读取仓库 [INSTALL.md](../INSTALL.md)，按照其中的固定版本与 7 个路径调用官方安装脚本，并处理已有目录、完整备份、文件核对和失败恢复。main 上维护的是安装指引，当前载荷固定到已发布的 `v0.4.0`；该 Markdown 文件不是可直接传给官方脚本的技能目录。

官方脚本没有 `--update`，遇到同名目录仍拒绝覆盖。统一入口通过 Codex 编排安装与升级步骤，不修改用户的系统 skill；本仓库项目安装器的 `--update` 是另一项已有能力，适用条件见下文。

## 手动复查：固定版本与安装器参数

本机官方安装器支持一次 `--path` 接收多个路径。需要手动安装到没有同名技能的目录时，完整参数如下；`<skill-installer目录>` 由 Codex 定位到本机实际路径：

```powershell
python "<skill-installer目录>/scripts/install-skill-from-github.py" --repo NingCui29/story-skill --ref v0.4.0 --path skills/story-codex skills/story-codex-plan skills/story-codex-write skills/story-codex-analyze skills/story-codex-review skills/story-codex-research skills/story-codex-cover
```

这份本机安装器默认安装到 `$CODEX_HOME/skills`，未设置时为 `~/.codex/skills`；其他 Codex 环境应核对其实际安装器与技能目录。只在一个项目使用时，可在同一请求中明确“安装到 `D:\小说\我的写作项目\.agents\skills`”；对应的 `--dest` 指向 **skills 父目录**，安装器创建 7 个子目录。它与下文项目安装脚本的 `--project` 参数含义不同。

**官方安装器遇到已有同名目录会拒绝覆盖。** 已有 0.3.0 或部分 0.4.0 时，先按升级说明处理旧目录与本地修改；多路径安装中途失败也要核对已完成项，不能把部分成功当成整套安装成功。

安装后核对 7 个目录都包含 `SKILL.md`，核心包含 `scripts/story.py` 和其余 4 个运行时模块，再在下一条消息使用 `$story-codex-plan` 或其他专用入口；未显示时重启 Codex。Python 要求为 3.10+，运行时仅用标准库；Codex 自身的账号和额度另计。

[套件 ZIP](https://github.com/NingCui29/story-skill/releases/download/v0.4.0/story-codex-0.4.0.zip) · [SHA-256 校验文件](https://github.com/NingCui29/story-skill/releases/download/v0.4.0/story-codex-0.4.0.zip.sha256)。该附件按 7 个同级技能打包，共 31 个文件；Source code ZIP 是 GitHub 自动生成的完整源码仓库，不能将整个仓库当成一个技能目录。

## 从源码安装到一个项目

技能唯一源码位于仓库 `skills/`，共 7 个同级目录。仓库根 `scripts/install.py` 负责把它们安装到目标项目的 `.agents/skills/`；`--project` 指向项目根，不是 skills 父目录。[完整目录职责](目录结构.md)

需要独立的固定版本源码时，先克隆到一个不存在的新目录：

```powershell
git clone --branch v0.4.0 --depth 1 https://github.com/NingCui29/story-skill.git story-skill-v0.4.0
```

在该 v0.4.0 源码仓库目录运行：

```powershell
python -B -X utf8 scripts/install.py --project "D:\小说\我的写作项目"
```

默认安装整套：`story-codex`、`story-codex-plan`、`story-codex-write`、`story-codex-analyze`、`story-codex-review`、`story-codex-research`、`story-codex-cover`。6 个专用技能读取同级核心的共同约束，使用核心的 `scripts/story.py`；不要分别复制不同版本。

若在开发仓库本身试用，运行 `python -B -X utf8 scripts/install.py --project "."`。根 `.agents/skills/` 是安装副本，受 Git 忽略；它不会替代 `skills/` 源码，也不会随源码编辑自动更新。克隆新版仓库后仍需安装，再在 Codex 的下一条消息调用技能；未显示时重启 Codex。

## 手动复查：从 0.3.0 升级到 0.4.0

日常升级直接使用上面的统一入口；以下说明供复查具体处理方式。所有安装均为文件副本，main 有新提交不会自动更新本机。先确认实际安装父目录和版本，再选择相同的安装方式；书目录无需搬动，技能安装也不会自动迁移书库。

| 当前安装方式 | 更新处理 |
|---|---|
| 本仓库 `scripts/install.py` 管理且未修改的安装 | 由安装器核对 `.story-codex-install.json` 清单，使用 `--update` 更新整套并保留备份 |
| 已有本地修改的托管安装 | 安装器停止覆盖；先完整保留旧目录与改动，再对照新版处理差异，不能删清单强行覆盖 |
| 官方 `$skill-installer` 安装 | 同名目录存在会拒绝覆盖；把旧目录与本地修改备份并移出扫描目录，再安装整套固定版本 |
| 手动复制或解压 | 不会自动获得项目安装器的托管清单；同样先在扫描目录之外保留完整副本，再按选定方式重新安装 |

仅第一种情况，在 **v0.4.0 源码仓库**目录运行：

```powershell
python -B -X utf8 scripts/install.py --project "D:\小说\我的写作项目" --update
```

安装器会将旧版保存到项目 `.agents/.story-codex-backups/` 下，并补齐 6 个新专用入口；以命令回执中的实际备份路径为准。其他安装方式备份时也要位于技能扫描目录之外，不能只在 `skills/` 内改成 `story-codex-old` 后继续让 Codex 扫描。保留本地改动的原文件和差异，核对新版后再决定如何恢复定制内容。

0.3.0 书库无需因这次技能拆分重新导入；更新操作只针对技能安装目录。新旧工具不要同时写同一本书，完成升级后再恢复写作。

## 补齐依赖与历史回退

核心缺失时，优先重新核对整套安装。若仅缺 `story-codex`，从**与其他 6 个技能相同的版本**补装 `skills/story-codex` 到同一 skills 父目录；不能把 v0.3.0 核心与新版专用技能配在一起。多路径安装未全部成功时先核对已存在的目录，官方安装器不会覆盖它们，不要把一条命令的部分输出当成整套完成。

用户级与项目级若同时存在同名技能，先明确本次使用哪一份，避免不同版本混用。不要直接改安装副本后期待改动进入源码仓库；需维护的技能改动回到 `skills/`，核对后再更新安装副本。

需要回退技能时，优先使用原安装备份；也可使用保留的旧单入口固定链接。先将当前整套技能移出扫描目录并完整保留，避免 0.4.0 专用入口继续搭配旧核心运行：

```text
$skill-installer https://github.com/NingCui29/story-skill/tree/v0.3.0/.agents/skills/story-codex
```

[v0.3.0 Release](https://github.com/NingCui29/story-skill/releases/tag/v0.3.0) 的 ZIP 内只有一个 `story-codex/`，共 13 个文件。旧版使用 `$story-codex`，没有 6 个新版独立入口。旧 `.agents/skills/story-codex` 源码路径只适用于该固定版本。技能回退不等于书库回退，恢复书籍状态应按 [恢复指南](recovery.md) 处理。

## 维护者：验证并发布新布局

本节说明可复用的发布顺序；具体执行结果以对应提交的 Actions、Release 和 Packages 回执为准。先核对 7 份入口和相对引用、整套安装/更新/恢复、ZIP 与 npm 白名单、新 token 输入清单及下载后的 CLI 验证。保留已发布版本的固定 tag、附件和历史测量，不覆盖已有版本。

在 PowerShell 中逐条运行并检查结果：

```powershell
git status --short
git remote -v
python -B -X utf8 scripts/smoke.py
python -B -X utf8 scripts/long_acceptance.py
python -B -X utf8 scripts/package.py
```

单元测试所需旧 ZIP 已随 [测试夹具](../tests/fixtures/README.md) 保存；历史实书迁移探针仍需另备旧数据库。`verify.py` 校验报告的当前哈希绑定。0.4.0 证据按版本保存到 `benchmarks/results/v0.4.0/`；当前 [token 重测](../benchmarks/results/v0.4.0/tokens.md) 已按 7 个入口统计。运行时迁移路径、流程拆分或文本变化后，不能只把 v0.3.0 通过数及 token 百分比改名为新版结果。

提交前检查 `skills/` 全部 7 个技能和发布工具进入暂存，旧 `.agents/skills/` 源文件的删除也已暂存；不要把本地安装副本、虚拟环境、数据库或测试产物放入提交。先审查完整 diff，再提交和推送。只有推送完成，main 的多路径安装入口才具备远端源码。

准备发布固定版本时，在实际通过验证的提交上创建未使用的版本 tag。核对运行时版本、ZIP 文件名、Release tag 和 npm 版本全部一致后，再推送 tag；不要强制移动已经分发的 tag。

在 [创建 GitHub Release](https://github.com/NingCui29/story-skill/releases/new) 选择新 tag，填写本版变化与真实验证范围，上传本次构建的 `story-codex-<版本>.zip` 和 `.zip.sha256`，再发布。`dist/` 被 Git 忽略，普通 push 不会上传附件。GitHub 自动生成的 Source code ZIP 包含整个仓库，与套件附件用途不同。

发布后使用固定 tag 在独立临时目录真实安装整套，核对文件与 ZIP 的逐字节一致性、共享依赖和 CLI 启动结果，再记录验证回执和发布状态。技能在 Codex 中的发现和任务路由需要实际使用验证，文件复制和 CLI 测试不能代替这一层。

## GitHub Packages 同步

[Packages](https://github.com/NingCui29/story-skill/pkgs/npm/story-codex) 使用 GitHub npm 注册表，`@ningcui29/story-codex@0.4.0` 已公开发布并完成回下载校验，详细证据见本页发布记录。仓库归属已核对为 `NingCui29/story-skill`；旧 `Cuinings` API 地址重定向到同一仓库 ID。新版工作流、包作用域、repository 元数据与安装链接均使用当前归属。npm 包不使用安装钩子注册 Codex；下载后不能当成已安装技能。

[同步工作流](../.github/workflows/packages.yml) 在正式 Release 发布时运行，也可在 [Actions](https://github.com/NingCui29/story-skill/actions/workflows/packages.yml) 手动选择已发布的新版本 tag 补同步。工作流从该 Release 的 ZIP 和 checksum 构建，使用仓库 `GITHUB_TOKEN` 的 `contents: read`、`packages: write` 权限。其他仓库触发会被拒绝。

历史 v0.3.0 的 13 文件布局、`@cuinings/story-codex` 身份及 npm 包装文件字节保持原样，可以构建校验；当前账号不会向旧作用域重新发布。2026-09-10 已从当前仓库的 v0.3.0 Release 实际下载、核对 ZIP/checksum、构建旧 npm 包并运行临时 CLI。该旧版准备结果不代表旧作用域当前的注册表权限或可见性已验证。

发布完成后回下载 npm tarball，核对 SHA-512、包身份、每个技能文件及共享依赖，再在临时工程运行核心的版本、帮助、初始化和状态检查。回执保存在 Actions artifact。重复同步先核对现有版本，内容不同则停止，不删除或覆盖。

仅构建验证已发布旧版而不上传：

```powershell
python -B -X utf8 scripts/sync_packages.py --tag v0.3.0 --prepare-only
```

按 GitHub npm 要求认证后，可下载已同步的 0.4.0 内容包：

```powershell
npm pack @ningcui29/story-codex@0.4.0 --registry=https://npm.pkg.github.com
```

包可见性与仓库可见性分别管理。GitHub npm 即使公开也需要认证下载；在 Codex 中优先使用前述技能安装方式。[GitHub npm 官方说明](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry)
