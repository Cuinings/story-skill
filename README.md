# Story Codex

面向 **Codex** 的中文小说技能包：开书、长短篇写作、拆文、审查、修改和资料研究。用一个入口、四份按需参考和本地状态工具，减少重复读规则、搬运整本设定、重新拆解已完成内容的成本。

这是分析 [oh-story-claudecode](https://github.com/zenstory-ai/oh-story-claudecode) 后独立编写的 **v0.2.0**。中文小说流程包含创作约定、人物知识与连续状态、明确计数口径、整篇短篇验收和多轮修订。作者说自然语言，Codex 负责工具与文件。[中文小说上手指南](docs/中文小说上手.md)

提供原创长篇连续三章与完整短篇，实际经过语义审查和 CLI 提交、修订、恢复、拆文验证。[中文实测报告](docs/中文实测.md) · [机器回执](benchmarks/results/chinese.json)。这是小规模真实稿件验证，**尚未用同题盲评证明文笔优于原项目**。

## 已测得的指令开销

固定上游提交 `4daac79077928d0d5ba0eda93e46ce68dfcd40ae`，用 `tiktoken 0.14.0 / o200k_base` 逐文件统计：

| 场景 | 上游 | Story Codex | 指令减少 |
|---|---:|---:|---:|
| 长篇单章明确必读指令下限 | 30,979 | 2,423 | 92.18% |
| 短篇：上游仅入口 vs 新版入口和流程 | 10,422 | 2,423 | 76.75% |
| 长篇拆文：上游仅入口 vs 新版入口和流程 | 8,996 | 1,621 | 81.98% |
| 审稿：上游仅入口 vs 新版入口和流程 | 11,334 | 1,633 | 85.59% |

这是**冷加载指令 token**，不是实际账单或一轮总 token。正文长度没有被压缩来制造节省；推理、工具结果、宿主提示、缓存、真实小说上下文和模型专用分词器未计入。上游已有按需读取与增量追踪，比较没有假设它每次加载全仓库。完整口径、文件哈希与合成召回实验见 [基准报告](benchmarks/results/tokens.md)。

## 直接使用

本项目已把技能放在 `.agents/skills/story-codex`，使用真实目录，无需 Windows 符号链接或安装 hooks。Codex 从项目 `.agents/skills` 发现技能；未出现时刷新技能列表或重新打开会话。[官方技能文档](https://learn.chatgpt.com/docs/build-skills)

在本项目中向 Codex 发送：

```text
$story-codex 在 D:\小说\新书 建立悬疑长篇设定和前三章细纲，不要写正文。

$story-codex 按已定细纲开始写 D:\小说\新书 的第1章，正文 2200—2800 字，含标点，不计标题。

$story-codex 完整分析 D:\素材\样本.txt，输出到 D:\小说\拆文\样本，包含番外，从断点继续。
```

普通语言也可匹配；已有同类技能同时启用时，建议显式点名 `$story-codex`，避免一次任务混用两套流程。当前工作没有卸载或改写你原来的全局 oh-story 技能；因此**发现阶段的旧技能元数据开销仍可能存在**。

安装到另一个小说项目（仅复制本技能，保留该项目配置）：

```powershell
python -X utf8 scripts/install.py --project "D:\小说\我的写作项目"
```

更新已有托管安装加 `--update`。工具核对源文件、暂存清单与原安装；复制或替换期间发现变化会停止，发现本地修改或未托管同名目录时拒绝覆盖。成功更新会在目标项目 `.agents/.story-codex-backups/` 保留旧版。同项目并发安装会被拒绝，安装锁随进程退出释放。[安装恢复说明](docs/recovery.md)

也可把 [独立技能压缩包](dist/story-codex-0.2.0.zip) 中的 `story-codex` 目录解压到目标项目 `.agents/skills/`；手动安装后再次升级也应按手动方式处理，不能把未托管目录当作安装器管理的副本。

## 写作数据怎样保存

每本书显式指定 `--book`。本地工具不调用 API，Python 3.10+ 标准库即可运行。

```text
书目录/
  设定.md、大纲.md               按实际需要创建的可读设计稿
  创作约定.md                    阶段、授权范围、不可改变项和下一动作
  .story/
    state.sqlite3               正文、计划、卡片、审查、来源和事件的权威存储
    drafts/                     修改中的正文和 JSON 提交材料
    analysis/<source-hash>/      已完成的分析报告导出
    export-backups/              替换导出时保留的文件版本
  chapters/0001.md              审查后正文导出
```

`context` 完整保留本章计划、指定卡片、全书硬限制、到期伏笔和上章衔接，只剔除不必加载的候选资料。预算按 UTF-8 字节计算且包含 JSON 内容；必要内容放不下会明确报错，不能用截掉限制来满足预算。正文事实的变化需要精确引文，审查记录绑定书 ID、状态版本和草稿哈希。

`prepare` 自动填入当前书籍、版本、稿件哈希，返回带待审阻断项的提交骨架。Codex 填写实际语义观察与变更，作者不需要处理这些字段。计数可选可见字符、字母数字或仅汉字，计划的口径实际控制 lint 和 commit；标题是否计入也有独立配置。导语计入正文，不将本地算法冒称平台后台统计。

`commit` 在一个 SQLite 事务中保存正文和状态，然后导出 Markdown。数据库已提交但导出失败（包括 SQLite 锁冲突）时返回 `committed: true, exports_complete: false`；解除故障后运行 `export` 或原命令重试，不会重复推进状态。

外部修改的最新原生章用 `reconcile` 读取修订上下文、核对稿件后提交。导出会复核文件、保留被换下的版本，并拒绝覆盖写入期间出现的新文件。Windows 使用同目录拒覆盖重命名，已在本机 D 盘 exFAT 实测完整中文稿件；POSIX 路径仍使用硬链接。完成回执表示导出后的核验通过，之后的外部修改由 `status` 检出。[恢复操作与边界](docs/recovery.md)

如果旧章缺失而最新章有外改，`export --safe-only` 可先恢复安全路径，再对账外改章；回执列出全部剩余问题，不把部分恢复报成完成。

只复制导出的正文不等于备份了全部状态；备份状态时应等待本地工具退出后复制整本书目录。拆文的纯空白块自动记录为无正文，保留原范围和哈希；旧断点执行 `next` 即可恢复，不重建编号或覆盖已有分析。

已有 oh-story 工程用独立目录建立续写基线；不会修改 `.active-book`、旧 `_progress.md`、hooks 或原文，也不要求先拆完整本书。详见 [写作流程](.agents/skills/story-codex/references/write.md)。

## 功能边界

| 能力 | 当前实现 |
|---|---|
| 开书、设定、长短篇写作 | Codex 流程 + 计划/状态工具 |
| 字数、稿件哈希、引用位置、并发版本 | 确定性校验 |
| 人物因果、连续性、自然度、原创判断 | Codex 语义审查，脚本不冒充质量裁判 |
| 原文拆解、番外保留、断点、报告 | 原文快照 + 无损切块 + 逐块证据记录 + 完成覆盖校验 |
| 旧书续写 | 只读原工程，建立独立末章/事实基线 |
| 最近一章修订 | 保留旧版事件，事务内回退旧增量再应用新增量 |
| 更早章节的历史重建 | 交付独立修订稿；复核后在新目录建立新基线，不自动级联回放 |
| 扫榜、联网查证 | 调用宿主已有工具的流程；不内置爬虫 |
| 封面 | 调用宿主现有图片工具；无工具时提供方案并说明缺口 |
| Dashboard、多平台部署、专门的 agent/hook 系统 | 不包含；本版只面向 Codex |

## 验证与复现

```powershell
python -X utf8 -m unittest discover -s tests
python -X utf8 scripts/smoke.py

# 仅 token 基准需要可选依赖；首次获取分词器可能下载其公开词表。
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
git clone https://github.com/zenstory-ai/oh-story-claudecode.git "<上游只读副本>"
git -C "<上游只读副本>" checkout 4daac79077928d0d5ba0eda93e46ce68dfcd40ae
.\.venv\Scripts\python.exe -X utf8 scripts/benchmark.py --upstream "<上游只读副本>"
python -X utf8 scripts/package.py
python -X utf8 scripts/verify.py
```

`verify.py` 实际运行回归测试、CLI 冒烟、真实中文稿件重放、临时项目安装与运行，并核对技能包内容、基准文件哈希及本地文档链接；测试数从执行结果生成，失败不会覆盖既有成功报告。[验证记录](benchmarks/results/verification.json)

`python -B -X utf8 scripts/upgrade_probe.py` 使用真实 v0.1.2 技能包验证升级到 v0.2.0、旧版备份完整性、安装清单一致性及重复更新。[升级记录](benchmarks/results/upgrade.json)

回归覆盖串书拒绝、版本冲突、重复提交、正文/状态事务回滚、并发保存保护、数据库锁后恢复、外部稿对账、修订增量撤回、Unicode/CRLF、空白块与旧断点恢复、拆文范围和安装更新。CLI 冒烟包含外部改稿修订及带番外的拆文报告全通路；它使用合成夹具，不代表真实模型的文学效果。

进一步阅读：[上游分析与设计取舍](docs/upstream-analysis.md) · [实际质量与用量评估方法](docs/evaluation.md) · [CLI 冒烟结果](benchmarks/results/smoke.json)

MIT License。上游采用 MIT；本实现未拷贝其小说 demo、参考教程或运行时代码。设计受到其公开流程启发，出处保留在分析报告中。
