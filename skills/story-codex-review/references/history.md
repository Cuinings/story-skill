# 历史分支、迁移与恢复

仅在更早章节、结构化世界增量章的修订，或旧版库迁移时读取；不是普通续写的必读流程。所有书籍命令调用共享 `<tool>` 并显式附加 `--book "<书目录绝对路径>"`，R 取最新 status。

需要理解或重绑定世界记录的字段与证据时，按需读 [世界状态说明](../../story-codex-write/references/long-form.md)；先 `world-read --kind facts --id ID`（可换其他类别）取回真实旧记录，不凭 ID 猜字段。分支所用依赖须来自实际复核；`dependencies --chapter N` 只给候选，不能直接宣称完整。`chapter-read --chapter N --sha256 SHA --start A --end B` 可定点读取当前或归档正文。

含世界增量的章及更早章用历史分支，不直接 replace-last 撤销局部卡片。`history-start --chapter N --expect R` 创建候选；按返回的影响范围、状态要求和 review_template 准备修订，用 `history-update` 保存，`history-inspect` 继续取断点。每个受影响章须刷新正文/摘要/依赖及审查，整个候选包另做状态和覆盖审查；`history-publish` 才发布。正文证据变化后的世界记录须在分支 world_changes 中重绑定，或用 retirements 明确撤销，并处理仍引用它的认知/规则。分支未发布时原版继续有效。

`history-inspect --branch B --chapter N` 返回该章基线/候选正文及空白 chapter_review_template；先读稿，再填观察和原句。一般 inspection 还给 state_review_template 的精确 before_sha/before，after 不预填：须明确填完整卡片以保持/修改，或 null 删除，并补候选章号、原句和理由。默认50张，可用 --state-offset/--state-limit 分页，单页最多200张。

start/update/refresh/inspect 的 affected、world、hints 三段共用 --limit，默认25、最大200；只有 inspect 用 --affected-offset、--world-offset、--hints-offset 分别续页，state 独立分页。读取 pages 中各段的 total/next_offset，next_offset 为 null 才到末页。complete 表示本次响应已含该段全部内容，非零 offset 的末页仍不完整。affected 分页时 review_template.reviewed_chapters 为 null，review_scope.chapter_ids_page 仅含当前页；收齐同一分支版本的全部范围并实际复核后，才能填全量 reviewed_chapters，不能把当前页当全书覆盖。

上述四命令及 history-state/cache-get 默认 --budget-bytes 64000，按 UTF-8 字节计。正文对照、审查凭据或缓存超限会报 budget_exceeded，不截断；可减小页数、用 chapter-read 分段读原文，或明确增大本次预算。缓存虽可保存至200000字节，读取仍受本次预算限制。

需要章前状态时用 `history-state --chapter N --before`，按 --offset/--limit 续取。它还原该出版 revision 的卡片状态，非故事时间状态，也不等于自动完成历史语义回放；不要从最新人物卡猜旧时状态。分支因外部进展过期可先 `history-refresh` 核对；依赖正文真正改变则重新建立分支，不只替换 revision/hash。

旧 schema 不自动升级。停止写入，保留整个书目录的独立拷贝，在副本上 `migrate`；保存返回的 `.story/migration-backups/` 一致性备份路径，再做 `audit`、`status` 和本章 context。回滚时停止全部书进程，把备份恢复到另一个独立书副本并使用旧版工具；迁移后的新章不在旧备份内，不能覆盖丢弃。切勿让新旧工具同时写同一本书。

合成容量测试、跨章编号模拟和脚本校验都不证明百万/千万字作品质量。实际连载仍逐章读稿，核对人物选择、代价、伏笔、公平信息和读者期待。
