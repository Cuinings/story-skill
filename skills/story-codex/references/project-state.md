# 项目状态与近期细纲

规划和正文写作共用本说明。命令调用 `story-codex/scripts/story.py`；所有书籍命令显式传入 `--book "<书目录绝对路径>"`，`R` 取最近一次 status 的 revision。

`template notes` 展示卡片结构。每张卡保存一个会影响后续的事实/人物状态/承诺，短而具体，带来源。少量全书硬限制用 `critical: true`；局部限制加 `scope: "volume:v1"（也可 arc/line/entity:ID）`，全局用 `global`；简单伏笔用 `kind: hook` 与 `due`；人物/地点设稳定 id 和 tags。作者习惯只有用户明确要求记住时才保存为 preference，不自动积累画像。

`notes --input "<卡片.json>" --expect R` 更新卡片，R 取 status。`kind` 仅支持 fact、character、world、hook、preference、contract。正文提交的 `changes` 复用卡片对象，每项另带 `quote` 精确原句，`source` 不能替代它。不要把整份大纲拆成无用卡片。

人物卡只存会影响下一步的已知/误信/未知及获知依据；作者掌握的谜底不等于人物知道。时间地点、物件归属、伤势、关系变化另用短事实卡；承诺写明触发条件或到期章。章末更新变化项，续写前核对这些状态和上章具体后果；有冲突定点补读，不把全书重新装入上下文。

`template plan` 展示计划结构；用 `plan --chapter N --input "<计划.json>" --expect R` 保存。保留用户原始要求在 `constraints`；填写目标、人物选择导致的场景变化、停笔点、字数范围、`requires`（所需卡片 id；结构化人物放 entities，不混填世界记录 id）及 tags。不要以“每场几个事件”“对白百分比”代替戏剧功能。未知事实不写成已确定设定。

把有作用的阻力、应对和代价写进现有 `beats.choice` / `beats.change` 描述，`goal` 说明本章要争取的结果与阅读期待；不另造“冲突分”“爽点数”字段。只记录能帮助写下一场的设计，不要求作者填写额外表格。

多卷、多视角和长期连载需要结构化世界资料时补读 [超长篇状态](../../story-codex-write/references/long-form.md)，只细化近期3—5章。
