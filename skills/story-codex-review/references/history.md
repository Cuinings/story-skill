# 历史分支、迁移与恢复

仅在更早章节、导入基线、结构化世界增量或证据绑定章、已合并历史分支章节、提交后相关卡片另有更新的修订，或旧版库迁移时读取；不是普通续写的必读流程。所有书籍命令调用共享 `<tool>` 并显式附加 `--book "<书目录绝对路径>"`，R 取最新 status。

需要理解或重绑定世界记录的字段与证据时，按需读 [世界状态说明](../../story-codex-write/references/long-form.md)；先 `world-read --kind facts --id ID`（可换其他类别）取回真实旧记录，不凭 ID 猜字段。建立分支后用 `history-dependencies --branch B --chapter N` 取该章依赖候选；普通 dependencies/context 不用于历史修订。结果含当前记录哈希及本分支已保存章节候选的哈希，不等于章前事实状态；实际读取、选择并补齐遗漏，处理 unavailable 后才能声明依赖完整。`chapter-read --chapter N --sha256 SHA --start A --end B` 可定点读取当前、归档或该章已保存的分支候选正文；它不会把候选发布为正文。

先核对目标章及受影响章的当前计划；导入基线通常还没有该章计划，按实际原文与本次授权补齐必要目标、停笔点、约束和容量，不虚构此前剧情。然后 `history-start --chapter N --expect R` 创建候选；若报 plan_missing，分支未建立，按回执先补缺失计划，再取最新 R 重试。已存在的旧候选若在建立后补改计划，须重新建分支，不能只刷新哈希。

按分支返回的影响范围、状态要求和 review_template 准备修订，用 `history-update` 保存，`history-inspect` 继续取断点。每个受影响章须刷新正文/摘要/依赖及审查，整个候选包另做状态和覆盖审查；`history-publish` 才发布。正文证据变化后的世界记录须在分支 world_changes 中重绑定，或用 retirements 明确撤销，并处理仍引用它的认知/规则；包含通过 world-save 后补的正文基线。分支未发布时原版继续有效。发布后用 `history-inspect` 分页条目的 `affected[].path` 定位当前托管正文（相对于书目录），即使重复发布时 `exported` 为空也可查到。该路径指向当前导出，基线与已保存候选版本仍按各自 SHA 定点读取。不能按章号猜文件名；旧工程仍识别原导出路径，不借历史修订批量搬动文件。

`history-inspect --branch B --chapter N` 返回所请求 N 章的 base/candidate 正文及空白 chapter_review_template；顶层 chapter 仍是分支起点，不能用它替代本次请求的章号。先读稿，再填观察和原句。一般 inspection 还给 state_review_template 的精确 before_sha/before，after 不预填：须明确填完整卡片以保持/修改，或 null 删除，并补候选章号、原句和理由。默认50张，可用 --state-offset/--state-limit 分页，单页最多200张。

`history-update --branch B --input "<候选更新.json>" --expect R` 的输入是对象，首次保存候选的结构如下；text 放完整候选正文，章号、摘要和依赖按本书实际内容填写：

```json
{"chapters":[{"chapter":1,"text":"<完整候选正文>","summary":"<本章实际变化>","dependencies":[],"complete":false}]}
```

随后读取该章 inspection，把填好的 `chapter_review_template` 放在对应 chapters 项的 `review` 中；text、summary 等未修改字段可省略。`complete` 表示依赖已实际核全，只有核对并补足依赖后才改为 true；跨章依赖指向此次分支中实际采用的正文 SHA。卡片决定放顶层 `state_changes` 数组，世界证据修复放 `world_changes` 对象，字段沿用前述模板与世界状态说明。先保存这些修改，再读取最新 `review_template`，实际复核全范围后作为顶层 `semantic_review` 保存。正文、摘要、依赖或状态变化会使旧审查失效，不能只换指纹；分支审查齐全后再 `history-publish`。

逐章审查的问题使用 blocker/advice；历史回执也兼容旧 minor/major，advice/minor 不阻断，blocker/major 必须解决后才能保存审查。不为通过校验把阻断问题降级；整个候选包的状态与覆盖审查仍须消除未解决问题。

最新章若返回 `revised_state_conflict`，说明其产生的卡片在提交后有新值，普通替换及 `reconcile` 都不能安全回滚。保留当前卡片与各版正文，取最新 R 后 `history-start --chapter N --expect R`；按 state_review_template 明确核对并保留、修改或删除卡片，不自动恢复为章前旧状态。存在外部改稿时，候选同时绑定本次实际读取的 external_sha256。

start/update/refresh/inspect 的 affected、world、hints 三段共用 --limit，默认25、最大200；只有 inspect 用 --affected-offset、--world-offset、--hints-offset 分别续页，state 独立分页。读取 pages 中各段的 total/next_offset，next_offset 为 null 才到末页。complete 表示本次响应已含该段全部内容，非零 offset 的末页仍不完整。affected 分页时 review_template.reviewed_chapters 为 null，review_scope.chapter_ids_page 仅含当前页；收齐同一分支版本的全部范围并实际复核后，才能填全量 reviewed_chapters，不能把当前页当全书覆盖。

上述四命令及 history-dependencies/history-state/cache-get 默认 --budget-bytes 64000，按 UTF-8 字节计。正文对照、审查凭据或缓存超限会报 budget_exceeded，不截断；可减小页数、用 chapter-read 分段读原文，或明确增大本次预算。读取候选须使用 affected[].draft_sha256 或 candidate.sha，不使用绑定摘要和依赖的 candidate_sha256。缓存虽可保存至200000字节，读取仍受本次预算限制。

需要章前状态时用 `history-state --chapter N --before`，按 --offset/--limit 续取。它还原该出版 revision 的卡片状态，非故事时间状态，也不等于自动完成历史语义回放；不要从最新人物卡猜旧时状态。分支因外部进展过期可先 `history-refresh` 核对；依赖正文真正改变则重新建立分支，不只替换 revision/hash。

旧 schema 不自动升级。停止写入，保留整个书目录的独立拷贝，在副本上 `migrate`；保存返回的 `.story/migration-backups/` 一致性备份路径，再做 `audit`、`status` 和本章 context。回滚时停止全部书进程，把备份恢复到另一个独立书副本并使用旧版工具；迁移后的新章不在旧备份内，不能覆盖丢弃。切勿让新旧工具同时写同一本书。

合成容量测试、跨章编号模拟和脚本校验都不证明百万/千万字作品质量。实际连载仍逐章读稿，核对人物选择、代价、伏笔、公平信息和读者期待。
