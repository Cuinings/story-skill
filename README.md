# Story Codex

面向 **Codex 的中文小说创作技能**：从开书、分卷规划、长短篇写作，到拆文、审稿和历史修订。作者用自然语言提出要求，Codex 负责计划、稿件、状态与证据；本地工具减少重复读取，并保留可恢复的创作进度。

**当前稳定版：v0.3.0** · Python 3.10+ · 标准库运行时 · MIT License

[版本说明](https://github.com/Cuinings/story-skill/releases/tag/v0.3.0) · [下载技能包](https://github.com/Cuinings/story-skill/releases/download/v0.3.0/story-codex-0.3.0.zip) · [SHA-256 校验文件](https://github.com/Cuinings/story-skill/releases/download/v0.3.0/story-codex-0.3.0.zip.sha256) · [中文上手指南](docs/中文小说上手.md) · [超长篇实操](docs/超长篇实操.md)

## 一行安装

在 **Codex 对话框**发送下面一行，安装已发布的固定版本：

```text
$skill-installer https://github.com/Cuinings/story-skill/tree/v0.3.0/.agents/skills/story-codex
```

仓库已公开，无须申请仓库访问权限。这一行交给 Codex 执行；内置安装器会安装完整技能及其资源。需要本机可用的 Python 3.10+，技能运行时无额外 Python 包或 API Key 要求；Codex 本身仍使用你的账号与额度。

安装完成后，在下一条消息中使用 `$story-codex`。若技能未显示，重启 Codex。[官方安装说明](https://learn.chatgpt.com/zh-Hans/docs/build-skills)

想使用 main 分支当前代码，将安装链接中的 `v0.3.0` 换成 `main`。这不会自动更新已有安装；同名目录已存在时，先保留旧版和本地修改，再按 [安装与升级说明](docs/github-release.md) 处理。

## 开始使用

以下路径可替换为你自己的小说目录。每本书独立保存，明确指定目标书籍。

**开长篇：先做规划**

```text
$story-codex 在 D:\小说\新书 建立一部计划300万字的中文悬疑长篇，先做创作约定、分卷规划和前三章细纲，不要写正文。
```

**续写：按已有断点推进一章**

```text
$story-codex 继续 D:\小说\新书，先核对创作约定和进度，再按细纲写下一章，正文2200—2800字，含标点不计标题，审查并保存后停止。
```

**审稿与修改**

```text
$story-codex 审查 D:\小说\新书 的第12章，重点检查人物认知、因果、伏笔和AI味，先列问题，不要直接重写。
```

**拆文：保留番外和断点**

```text
$story-codex 完整分析 D:\素材\样本.txt，输出到 D:\小说\拆文\样本，包含番外；如已有进度，从断点继续，不覆盖已完成分析。
```

短篇创作、修改和资料研究也可用自然语言提出。已安装其他同类技能时，显式点名 `$story-codex`，避免在同一任务混用不同状态流程。

## v0.3.0 能做什么

| 范围 | 当前能力 |
|---|---|
| 中文长短篇 | 创作约定、设定、大纲、章节计划、正文、完整短篇和多轮修订；字数口径可配置 |
| 分卷与多线 | 按卷、情节段、故事线和实体取资料；切线接回该线的最后场景与未完动作 |
| 人物认知 | 区分知道、相信、怀疑和有证据的明确不知；按故事时间处理倒叙 |
| 远期伏笔 | 保存铺垫、强化、休眠、履约等变化，关联实体与故事线召回 |
| 规则与资源 | 规则版本、生效区间、使用条件、冷却与精确数量账；未知信息保持未知 |
| 中文检索 | 单字、两字姓名的字符索引，回读原文确认；同名和别名用稳定实体 ID 消歧 |
| 历史改稿 | 候选分支、依赖影响、逐章审查、世界证据修复和快照；数千章影响范围分页读取 |
| 保存与恢复 | 正文和状态同事务提交，版本核对、重复提交保护、导出恢复及旧库显式迁移 |
| 原文拆解 | 来源快照、无损切块、逐块证据、完成覆盖检查，保留番外和中断进度 |

资料研究与封面流程使用宿主已有工具。本包只面向 Codex，不包含爬虫、Dashboard 或多平台部署系统。因果、文风、原创性和读者体验仍由实际读稿与语义审查判断，脚本不自动证明文学质量。

## 百万／千万字长篇

每章只装入本次需要的计划、人物和世界状态；未来方案与正文已发生的事实分开。必要资料放不进预算时明确报错，不能静默丢掉限制。历史修订按影响范围分页，当前页完成不能冒充全范围已审。[完整流程](docs/超长篇实操.md)

v0.3.0 的容量探针已完成以下两种规模，均分别验证 strict / local 模式：

| 合成正文规模 | 章节数 | 状态卡数 | 结果 |
|---|---:|---:|---|
| 100 万字 | 400 | 2,000 | 通过 |
| 1,000 万字 | 4,000 | 20,000 | 通过 |

默认 **strict** 完整哈希核验历史导出，成本随全书增长。显式使用 `--integrity local` 时，只核验当前和待导出文件；在上述夹具中，获取本章上下文读取 1 次正文文件，提交下一章读取 3 次。它会报告未核验的历史数量，`exports_complete: null` 不表示全书已核验。新会话、故障恢复、外部改稿和阶段交付应运行完整 `audit`。

这些是重复汉字与受控状态的合成容量结果，尚不等于完成了千万字小说的长期创作验证。[容量原始数据](benchmarks/results/scaling-v0.3.json) · [超长篇验收与边界](docs/超长篇验收.md)

## 指令 token 开销

固定对比 [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) 提交 `4daac79077928d0d5ba0eda93e46ce68dfcd40ae`，使用 `tiktoken 0.14.0 / o200k_base` 逐文件统计：

| 场景与统计口径 | 上游 | Story Codex | 指令减少 |
|---|---:|---:|---:|
| 长篇单章：上游明确必读指令下限 | 30,979 | 2,547 | 91.78% |
| 多线超长篇：新版含完整超长篇附加流程 | 30,979 | 4,965 | 83.97% |
| 短篇：上游仅入口，新版入口与流程 | 10,422 | 2,547 | 75.56% |
| 长篇拆文：上游仅入口，新版入口与流程 | 8,996 | 1,682 | 81.3% |
| 审稿：上游仅入口，新版入口与流程 | 11,334 | 1,683 | 85.15% |

统计的是**冷加载指令 token**，不包括正文输出、推理、工具结果、宿主提示和真实小说上下文，不代表总账单降幅。上游也有按需读取和增量追踪；这里没有假设它每次加载全仓库，也未通过压缩正文长度制造节省。其他技能仍启用时，它们的发现元数据开销也仍可能存在。[完整口径与文件哈希](benchmarks/results/tokens.md)

## 保存、升级与项目安装

每本书的 `.story/state.sqlite3` 保存正文、计划、状态和事件；`chapters/` 中的 Markdown 是便于阅读的导出。备份时等待书籍工具退出，再复制完整书目录，只复制正文不能保留全部状态。

正文已提交而导出失败时，回执会明确区分两者；解除故障后执行 `export` 或重试原命令，不会重复推进章节。检测到外部改稿时先对账，保留版本后再修订。[恢复指南](docs/recovery.md)

**从 v0.2.0 升级：**技能安装与书库迁移分开。旧书库为 schema1；先保留独立副本，在副本执行 `migrate`，再核对导出和创作断点。不要让新旧工具同时写同一本书。[迁移与回滚步骤](docs/超长篇实操.md)

只想在一个项目使用本技能，可先克隆仓库，再从仓库目录运行：

```powershell
python -X utf8 scripts/install.py --project "D:\小说\我的写作项目"
```

该工具将技能安装到目标项目 `.agents/skills/story-codex`。只有由它管理、且没有本地改动的安装才可用 `--update` 更新，更新时保留旧版备份。官方 `$skill-installer` 和手动解压的安装不使用这份托管清单。

手动安装可下载本页顶部的技能 ZIP，将其中的 `story-codex` 目录放入目标项目 `.agents/skills/`。下载包包含 13 个文件；GitHub 的自动 Source code ZIP 则包含整个仓库。克隆本仓库并在其中使用 Codex 时，项目内已具备技能目录。

## 验证与开发

v0.3.0 发布前，**226 项测试、12 项整包检查全部通过**。另有实际中文稿件重放、75 次 CLI 调用的多线修订演练、三个旧工程副本迁移，以及 GitHub main / v0.3.0 的实际安装验证。GitHub 安装的 13 个技能文件与发布 ZIP 逐字节一致；这次验证涵盖版本、帮助、初始化和状态读取。

[整包验证记录](benchmarks/results/verification.json) · [中文实稿](docs/中文实测.md) · [多线修订演练](benchmarks/results/long-acceptance.json) · [旧工程迁移](benchmarks/results/migration-v0.3.json) · [安装升级](benchmarks/results/upgrade.json)

新 clone 可运行自行创建临时工程的 CLI 检查，以及技能打包：

```powershell
python -B -X utf8 scripts/smoke.py
python -B -X utf8 scripts/long_acceptance.py
python -B -X utf8 scripts/package.py
```

完整单测需要本地保留的 `dist/story-codex-0.2.0.zip`，这个旧包没有放入 Git。`verify.py` 还会核对现有容量、迁移等报告与当前代码的哈希绑定，不会重跑这两项探针。先准备对应旧包与报告，再运行：

```powershell
python -B -X utf8 -m unittest discover -s tests
python -B -X utf8 scripts/verify.py
```

运行时仅依赖 Python 标准库；复现 token 基准才需要 `requirements-dev.txt` 中的可选依赖和固定上游副本。容量探针为 `scripts/scale_probe.py`；重跑迁移探针 `scripts/migrate_probe.py` 还需要三个未入 Git 的旧示例数据库。新 clone 的冒烟检查不能代替完整历史验收。[发布与安装说明](docs/github-release.md) · [质量和实际用量评估方法](docs/evaluation.md)

## 项目来源与许可

本项目分析 oh-story-claudecode 的公开流程后独立实现，保留 [上游分析与设计取舍](docs/upstream-analysis.md)。未拷贝其小说 demo、参考教程或运行时代码。当前已有小规模中文实稿验证，尚未通过同题盲评证明文笔优于原项目。

采用 [MIT License](LICENSE)。
