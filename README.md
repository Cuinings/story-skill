# Story Codex

**平台：本版面向 macOS／Linux。Windows 正文与报告导出的已知 WinError 32 尚未修复，Windows 用户继续使用 [v0.4.0](https://github.com/NingCui29/story-skill/releases/tag/v0.4.0)。** 已用新版处理的书先完整备份，不盲目降级。

面向 **Codex 的中文小说技能套件**。按开书规划、正文写作、作品分析、审稿、资料研究和封面分工，共用一套断点、状态和证据工具。作者用自然语言提要求，Codex 维护稿件和进度。

**v0.5.2 已发布：大纲规范、状态保护与修订恢复。** 七个技能共 33 个文件，明确全书总纲、具名卷纲和逐章细纲，修复约束卡片更新、世界状态判定、历史修订及分析并行保存的问题。保留作品深读、按需示范和具名分卷正文。[版本说明](docs/releases/v0.5.2.md) · [实际发布状态](docs/github-release.md)。Python 3.10+ · 标准库运行时 · MIT License。

已完成两轮探索性评估、争议修订、迁移试用及《阿Q正傳》完整九章试用；程序核验与独立模型评阅分开记录，不宣称“大师级”认证或稳定质量提升。[作品深读与评估](docs/作品深读与评估.md)

[文档导航](docs/README.md) · [目录结构与职责](docs/目录结构.md) · [中文上手指南](docs/中文小说上手.md) · [超长篇实操](docs/超长篇实操.md) · [安装与发布](docs/github-release.md) · [历史 v0.5.1](docs/releases/v0.5.1.md) · [历史 v0.5.0](docs/releases/v0.5.0.md)

v0.5.2 汇总 2026-09-11 的规范与运行时修正。细纲按卷、按章维护当前入口，旧版归档；已采用细纲与工具计划同步，卷内硬限制核对实际召回。世界状态保留时间歧义，历史修订保护后补证据；分析替换与首次定稿需要所依据分析的指纹。详见 [大纲细纲怎样保存](docs/中文小说上手.md#大纲细纲怎样保存)、[超长篇实操](docs/超长篇实操.md) 与 [恢复流程](docs/recovery.md)。本版于 2026-09-11 发布，验证单独登记在 [v0.5.2 记录](benchmarks/results/v0.5.2/README.md)；本机 macOS 与远端 Linux 通过，Windows 保留已知导出失败。历史测量保持各自版本范围。

## 先分清三个目录

| 目录 | 放什么 | 由谁维护 |
|---|---|---|
| 仓库 `skills/` | 7 个技能的唯一源码、流程和共享运行时 | 开发者修改并提交 Git |
| 写作项目 `.agents/skills/` | 安装器复制的 7 个技能，供 Codex 发现与调用 | 安装器安装、核对与更新 |
| 用户指定的书目录 | 创作约定、大纲、`chapters/` 正文、`.story/` 状态与草稿 | Codex 按本次写作授权维护 |

```text
story-skill/                         # 开发仓库
├── skills/                         # 技能源码
│   ├── story-codex/                 # 总入口、共同约束、共享工具
│   ├── story-codex-plan/            # 开书、设定、大纲、导入基线
│   ├── story-codex-write/           # 长短篇正文与续写
│   ├── story-codex-analyze/         # 拆文与分析断点
│   ├── story-codex-review/          # 审稿、修改、去 AI 味
│   ├── story-codex-research/        # 扫榜与资料查证
│   └── story-codex-cover/           # 封面构思与生成
├── scripts/                        # 安装、打包、验收与发布工具
├── tests/                          # 软件测试
├── docs/                           # 作者与维护者文档
└── benchmarks/                     # 性能口径与测量证据

/Users/作者/小说/我的写作项目/
├── .agents/skills/                 # 安装后的 7 个同级技能目录
└── 新书/                           # 明确指定给 --book 的书目录
    ├── 创作约定.md
    ├── chapters/                   # 按分卷保存的正文导出
    │   └── 第一卷 雨夜/
    │       └── 第1章 雨中来客.md
    └── .story/                     # 状态数据库、草稿与恢复资料
```

技能内部的 `scripts/` 是小说运行工具；仓库根部的 `scripts/` 是开发与分发工具。源码迁到 `skills/` 后，克隆仓库本身不等于已安装技能；需要运行安装器。卷目录名固定为 `第X卷 卷名`，例如 `第一卷 雨夜`、`第二卷 归途`，必须包含卷名；短篇与单卷作品也先明确首卷名称。正文文件名固定为 `第N章 章节名称.md`，N 使用不补零的阿拉伯数字。完整职责和放置规则见 [目录说明](docs/目录结构.md)。

## 安装与升级

首次安装、补齐技能或从旧版升级，都在 Codex 对话框发送同一行：

```text
$skill-installer 按 https://github.com/NingCui29/story-skill/blob/main/INSTALL.md 安装或升级 Story Codex
```

Codex 先读取 [安装指引](INSTALL.md)，再调用官方安装脚本，自动展开完整 7 个技能路径、核对已有安装并保留升级备份与本地修改。指引位于 main，目标技能载荷固定为 `v0.5.2`，无需用户列出 7 个路径。macOS／Linux 使用 v0.5.2；Windows 暂用固定 v0.4.0，安装器按平台选择并核验附件。

本机官方安装器默认放到 `$CODEX_HOME/skills`（未设置时为 `~/.codex/skills`）；其他环境请以其安装器和实际技能目录为准。官方脚本仍会拒绝覆盖同名目录，升级处理由 Codex 按指引编排，**没有给官方脚本增加 `--update` 参数，也不修改系统 skill**。完成后下一条消息即可点名使用；未显示时重启 Codex。[手动安装参数与升级细节](docs/github-release.md)

v0.5.2 套件附件名为 `story-codex-0.5.2.zip`，附独立 SHA-256 校验文件，共 7 个技能、33 个文件。[Release 与附件](https://github.com/NingCui29/story-skill/releases/tag/v0.5.2) 按 [安装指引](INSTALL.md) 核验；Release 附件已回下载，33 个技能文件与源码、本地包及官方固定标签隔离安装逐字节一致，四项运行时检查通过；注册表结果单独见 [发布记录](docs/github-release.md)。GitHub 自动生成的 Source code ZIP 是整个源码仓库；历史版本附件保持原样。

6 个专用技能依赖同级的 `story-codex`：共同约束和 `scripts/story.py` 只维护一份。优先整套安装，避免只下载一份 `SKILL.md`。缺少核心时，在同一安装父目录补装同一版本的 `story-codex`；已有同名技能先保留旧版与本地修改，不能混用新专用技能和 v0.3.0 核心。

0.3.0／0.4.0 书库无需重新导入，升级只处理技能。已有平铺或旧名称正文仍按登记路径读取与恢复，不会自动批量搬动；新增正文遵守具名分卷与章节命名规则。旧版与本地修改保存在技能扫描目录之外；保留修改不等于已经将其合并到新版。[完整升级与恢复说明](docs/github-release.md)

### 安装到指定写作项目

macOS／Linux 在 **v0.5.2 源码仓库**目录运行以下安装命令；Windows 使用 v0.4.0 源码。

```bash
python3 -B -X utf8 scripts/install.py --project "/Users/作者/小说/我的写作项目"
```

安装目标是该项目的 `.agents/skills/`，每个技能各占一个同级目录。想在开发仓库内试用，可将 `--project` 设为 `"."`；生成的根 `.agents/skills/` 是被 Git 忽略的安装副本，修改技能仍应回到 `skills/`。

### 历史版本与回退：v0.3.0

需要旧单入口版本时，使用保留的固定 tag。先把当前整套技能移出扫描目录并完整保留，避免新版专用入口继续搭配旧核心运行：

```text
$skill-installer https://github.com/NingCui29/story-skill/tree/v0.3.0/.agents/skills/story-codex
```

[下载 v0.3.0 技能 ZIP](https://github.com/NingCui29/story-skill/releases/download/v0.3.0/story-codex-0.3.0.zip) · [SHA-256 校验文件](https://github.com/NingCui29/story-skill/releases/download/v0.3.0/story-codex-0.3.0.zip.sha256)。这个旧包包含 13 个文件，使用 `$story-codex`，不包含新版 6 个专用入口。固定 tag 和附件保留原样。

## 按工作调用技能

不确定用哪个入口时，使用 `$story-codex` 描述目标；任务明确时直接点名专用技能，按需读取相应流程。

| 入口 | 负责的事 |
|---|---|
| `$story-codex` | 判断任务、读取共同约束、定位书籍断点与共享工具 |
| `$story-codex-plan` | 开书、创作约定、人物设定、分卷与细纲、已有小说导入基线 |
| `$story-codex-write` | 长短篇正文、逐章续写、长度核对、审查后提交 |
| `$story-codex-analyze` | 小说拆解、来源证据、逐块分析、断点恢复与汇总 |
| `$story-codex-review` | 审稿、最小修改、去 AI 味、外部改稿对账与历史修订 |
| `$story-codex-research` | 榜单研究、题材资料、事实查证与来源记录 |
| `$story-codex-cover` | 书名署名、封面构思、调用可用图片工具并验收图片 |

**先规划，不写正文：**

```text
$story-codex-plan 在 /Users/作者/小说/我的写作项目/新书 规划一部300万字中文悬疑长篇，完成创作约定、分卷规划和前三章细纲，不要写正文。
```

**按断点写下一章：**

```text
$story-codex-write 继续 /Users/作者/小说/我的写作项目/新书，先核对创作约定和进度，再按细纲写下一章，正文2200—2800字，含标点不计标题，审查并保存后停止。
```

**审稿或拆文：**

```text
$story-codex-review 审查 /Users/作者/小说/我的写作项目/新书 的第12章，检查人物认知、因果、伏笔和AI味，先列问题，不要直接重写。
$story-codex-analyze 完整分析 /Users/作者/素材/样本.txt，输出到 /Users/作者/小说/拆文/样本，保留番外；如已有进度，从断点继续，不覆盖已完成分析。
```

**查资料或做封面：**

```text
$story-codex-research 为 /Users/作者/小说/我的写作项目/新书 查证故事中要用的铁路调度流程，记录来源和未知项。
$story-codex-cover 为 /Users/作者/小说/我的写作项目/新书 设计封面，书名《雾港来信》，作者署名“某某”，先读取本书题材与上传要求。
```

各入口沿用同一本书的状态，切换任务无需重新导入或创建第二份书库。研究、封面依赖宿主已有工具；运行时没有额外 Python 包或 API Key 要求，Codex 及图片工具仍使用各自的账号、额度与能力。

## 中文写作：冲突与看点

规划时把人物想要的东西、有效阻力和难以兼得的选择落到具体场景；写作时展开尝试、回应与后果，让破局、关系变化或真相揭示发生在正文里。中文对白关注身份、亲疏、共同经历与潜台词，长篇关注阻力和解法是否反复。温暖日常和安静余波同样成立，不强塞争吵、恶人或章末惊吓。

这套指导接入了规划、正文和针对性审稿，共用一份 [中文场景指导](skills/story-codex-write/references/drama.md)。正文前读取，已经加载的同版内容复用；只校对或只审不改的授权仍然有效。

```text
$story-codex-review 第12章矛盾和看点不足。结合原文定位目标、阻力、人物选择和读者期待落空的位置，区分需要修的平淡与有意的安静，只列问题和修改建议。
```

首轮做了修改前后两题、四篇中文场景的匿名代理评阅：交锋题打平，温和日常题轻微偏好旧稿。它发现了新版情节过于整齐和人物声线偏通用的问题，随后据此细修并另做留出题试用；**尚未证明新版文学质量整体更高**。[修改说明、完整样稿与原始评阅](docs/中文冲突与看点.md)

v0.4.0 验收另完成《空船照夜》连续三章与新会话第4章续写，共 9,297 字；两轮独立语义审查未发现确定矛盾，并保留歧义与节奏建议。原稿、工具回执、指令哈希和评阅全部归档。这是单故事功能与语义试用，不是同题优胜或长程质量证明。[全仓修复与连续章节实测](docs/全仓审查与优化.md)

## 中文长篇与百万／千万字连载

支持分卷、多故事线、人物认知、远期伏笔、规则版本、精确资源账、中文实体检索和历史修订分支。每章只读取本次计划、相关人物和世界状态；未来方案与正文事实分开，必要资料超预算时明确报告，不能静默丢掉限制。历史修订按影响范围分页复核。[超长篇实操](docs/超长篇实操.md)

默认 `strict` 完整哈希核验历史导出，成本随全书增长。显式使用 `--integrity local` 时只核验当前和待导出文件，并报告未核验的历史数量；`exports_complete: null` 不表示全书通过。新会话、故障恢复、外部改稿与阶段交付运行完整 `audit`。

**v0.5.2 已重新完成百万／千万字合成容量检查：**

| 合成正文规模 | 章节数 | 状态卡数 | v0.5.2 结果 |
|---|---:|---:|---|
| 100 万字 | 400 | 2,000 | strict / local 均通过 |
| 1,000 万字 | 4,000 | 20,000 | strict / local 均通过 |

这些是重复汉字与受控状态的容量夹具，四种规模／模式组合均通过，必需内容超预算时明确拒绝。它们不能等同于千万字小说的长期创作验证，也不提供吞吐保证。[v0.5.2 容量原始数据](benchmarks/results/v0.5.2/scaling.json) · [v0.5.1 历史容量](benchmarks/results/v0.5.1/scaling.json) · [v0.5.0 历史容量](benchmarks/results/v0.5.0/scaling.json) · [v0.4.0 历史容量](benchmarks/results/v0.4.0/scaling.json) · [验收边界](docs/超长篇验收.md)

## Token 与验证证据

以下是 v0.5.2 重新测量的完整技能与共同依赖指令，固定对比上游提交 `4daac79077928d0d5ba0eda93e46ce68dfcd40ae`，使用 `tiktoken 0.14.0 / o200k_base`：

| 场景 | 上游冷加载指令 | v0.5.2 冷加载指令 | 指令减少 |
|---|---:|---:|---:|
| 长篇单章：上游明确必读下限 | 30,979 | 6,324 | 79.59% |
| 多线超长篇：新版含条件附加流程 | 30,979 | 8,511 | 72.53% |
| 短篇：上游仅入口，新版含流程 | 10,422 | 6,324 | 39.32% |
| 全篇深读：上游仅入口，新版含深读规范 | 8,996 | 4,959 | 44.88% |
| 深读示范：再含按需教学对照 | 8,996 | 6,968 | 22.54% |
| 审稿：上游仅入口，新版含流程 | 11,334 | 2,868 | 74.70% |
| 冲突与看点审查：额外读取场景指导 | 11,334 | 4,198 | 62.96% |

七个技能名称与描述共 **313 tokens**，另行统计。较 v0.5.1，普通／多线写作增加 994／1,414 tokens，深读及含示范各增加 441 tokens，用于补齐规划同步、状态与修订恢复要求。公共指导在同一上下文中复用，按需参考按实际任务加载。[v0.5.2 基准与哈希](benchmarks/results/v0.5.2/tokens.md) · [历史 v0.5.1](benchmarks/results/v0.5.1/tokens.md) · [历史 v0.5.0](benchmarks/results/v0.5.0/tokens.md) · [历史 v0.4.0](benchmarks/results/v0.4.0/tokens.md)

统计不含正文、推理、工具结果、宿主提示或实际小说上下文，不代表总账单降幅；也不能据此证明小说质量更高。旧技能仍启用时，它们的发现开销也仍然存在。[实际用量与质量评估方法](docs/evaluation.md)

v0.5.2 发布版已完成本机 Intel macOS／Python 3.12 的 443 项测试：436 项通过、7 项按条件跳过、零失败；12 项整包检查通过。[最终 CI 34577137667](https://github.com/NingCui29/story-skill/actions/runs/34577137667) 的 Linux 443 项中 431 项通过、12 项按平台跳过，全部步骤成功；Windows 首项测试遇到已知 WinError 32 后停止，整体 CI 因此为失败，不宣称全平台通过。[本版验证记录](benchmarks/results/v0.5.2/README.md) 分别保存平台及分发证据；下列历史结果不替代本版执行。

历史 v0.5.1 本地 397 项测试中 390 项通过、7 项按条件跳过，12 项整包检查通过；远端 Linux 397 项中 385 项通过、12 项按平台跳过，全部步骤成功。旧版套件升级、三类合成旧库迁移和四种容量组合通过；完整工程检查和远端分发状态见 [v0.5.1 验证记录](benchmarks/results/v0.5.1/README.md)。分析专项覆盖合成材料、两篇真实短篇及《阿Q正傳》九章，独立模型评阅保留原稿、争议与限制。[分析证据](docs/作品深读与评估.md)

历史 v0.5.0 已完成正式 v0.4.0 套件到 v0.5.0 的真实安装升级，18 项检查通过，覆盖完整旧版保留、七入口更新、重复升级不重复写入、书籍和其他技能不变。另用固定 v0.2.0 工具生成长篇、短篇导入和拆文三类 schema 1 中文夹具，验证迁移与回滚；本机缺少原有三本旧库，本次结果不能称为历史实书重验。[v0.5.0 升级回执](benchmarks/results/v0.5.0/upgrade.json) · [合成旧库迁移](benchmarks/results/v0.5.0/migration.json)。修复后的本地 macOS／Python 3.12 回归完成 **379 项测试：372 项通过、7 项平台专用测试跳过、零失败或错误**。同一代码的 12 项整包检查和四组合容量复验全部通过。[最终验收回执](benchmarks/results/v0.5.0/verification.json)。[远端 CI](benchmarks/results/v0.5.0/release/ci.json) 的 Linux 检查通过；Windows 导出仍有已知失败。已用 v0.5.0 处理的书先完整备份，不盲目降级。[发布记录](docs/github-release.md)

**v0.3.0 发布前**完成 226 项测试、12 项整包检查，以及中文实稿重放、75 次 CLI 调用的多线修订演练、三个旧工程副本迁移和 GitHub 安装核对。旧版安装的 13 个文件与当时 Release ZIP 一致。这些数字只描述 v0.3.0 验收，不代表后续版本结果。

**历史 v0.4.0 在本地干净检出中通过 311 项测试和 12 项整包检查**，覆盖 7 个技能入口、31 个分发文件、安装后的 CLI、中文稿件与多线演练。另已完成 v0.3→v0.4 整套升级、百万／千万字容量复验及独立代理的只读审稿试用；该试用验证显式调用后的路由与原稿保护，不代表新会话自动发现或小说质量盲评。[v0.4.0 验证回执](benchmarks/results/v0.4.0/verification.json) · [升级验证](benchmarks/results/v0.4.0/upgrade.json) · [路由试用](benchmarks/results/v0.4.0/routing.json)

[历史中文实稿](docs/中文实测.md) · [多线演练记录](benchmarks/results/long-acceptance.json) · [v0.3 迁移证据](benchmarks/results/migration-v0.3.json)

## 保存、更新与开发

v0.5.0 曾补齐 Windows 大小写等价路径检查、目录句柄权限和异常 ZIP 路径拒绝。开书时将数据库表与初始元数据放入一次事务，失败则回滚数据库改动，保留原有持久化设置；新增初始化回滚与可见性回归。八次本地初始化测量仅描述 macOS 样本，不代表 Windows 或 CI 总耗时。[初始化证据](benchmarks/results/v0.5.0/initialization.json)

每本书的 `.story/state.sqlite3` 保存正文、计划、状态和事件，`chapters/` 中的 Markdown 是可阅读的导出。备份时等待书籍工具退出，再复制完整书目录；只复制正文不能保留全部状态。正文已提交而导出失败时按回执运行 `export` 恢复。外部改稿先对账并保留版本。[恢复指南](docs/recovery.md)

技能更新与书库迁移分开：新增正文的分卷和命名规则不意味着重新导入书籍，也不会自动整理既有导出。章节实际路径以命令回执为准，不按编号猜测文件名。升级已有安装时，保留旧版和本地修改，使用对应安装方式更新整套技能；不要让新旧工具同时写同一本书。需要迁移旧书库时在独立副本上操作。[安装、升级与发布说明](docs/github-release.md)

源码开发与验证工具位于仓库根 `scripts/`。以下命令在仓库目录运行，CLI 检查自行创建临时工程：

```bash
python3 -B -X utf8 scripts/smoke.py --output dist/manual-smoke-v0.5.2.json
python3 -B -X utf8 scripts/long_acceptance.py --output dist/manual-long-v0.5.2.json
python3 -B -X utf8 scripts/package.py
```

单元测试所需的旧版迁移 ZIP 已作为带 SHA-256 的 [固定夹具](tests/fixtures/README.md) 随仓库保存，新 clone 可直接运行 `python3 -B -X utf8 -m unittest discover -s tests`。[CI](.github/workflows/ci.yml) 配置了 Linux/Python 3.10 与 Windows/Python 3.12 的回归、打包和冒烟检查，远端执行结果以 Actions 为准。CI 还包含已审中文样稿与多线历史修订的 CLI 演练；样稿固定 LF 检出以保留原审稿哈希。`migrate_probe.py` 默认用固定旧工具生成长篇、短篇导入和拆文三类 schema 1 合成夹具，无需另备旧库；用 `--source` 复查历史实书时才需要提供保留的旧数据库。完整验证核对报告与当前文件的哈希绑定；复现 token 基准需要 `requirements-dev.txt` 中的可选依赖与固定上游副本。

## GitHub Packages 与许可

当前仓库为 [NingCui29/story-skill](https://github.com/NingCui29/story-skill)，v0.5.2 对应 npm 包 `@ningcui29/story-codex@0.5.2`。本版 Release 与公开 GitHub Packages 均已发布；ZIP、npm 回下载的 33 个技能文件与源码一致，npm 的 2 个包装文件也匹配，官方固定标签隔离安装和独立运行检查通过，实际完成状态见 [发布记录](docs/github-release.md)。历史 v0.5.0 的公开包、31 个技能文件与四项 CLI 检查保留 [原回执](benchmarks/results/v0.5.0/release/package-check.json)，不能替代本版结果。Codex 安装优先使用固定 tag 或套件 ZIP；npm 不会自动注册技能，GitHub npm 下载仍需认证。

本项目分析 [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) 的公开流程后独立实现，未拷贝其小说 demo、参考教程或运行时代码。尚未通过同题盲评证明文笔优于原项目。[上游分析与设计取舍](docs/upstream-analysis.md) · [MIT License](LICENSE)
