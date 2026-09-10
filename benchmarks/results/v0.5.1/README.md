# v0.5.1 发布验证

此目录保存本版重新执行的发布检查，不覆盖历史回执。逐项分发状态见 [发布状态](release/state.json)，功能、兼容和平台范围见 [版本说明](../../../docs/releases/v0.5.1.md)。

- [ZIP 构建](package.json)：七个技能、33 个载荷文件，SHA-256 与此前最后一次分析试用的技能快照一致。
- [npm 构建](npm-package.json)：技能载荷与 ZIP 绑定，新增本版平台提示，历史 wrapper 保持原字节。准备时缺少校验文件、npm 不在路径及现有 npm 启动器路径不匹配的三次失败分别保存在 npm-package-first-failed.json、npm-package-second-failed.json、npm-package-third-failed.json；随后使用现有 npm 的 JS 入口完成构建。
- [v0.5.0→v0.5.1 整套升级](upgrade.json)：在隔离工程验证新版文件、旧版备份、重复升级和小说保护。
- [旧库迁移与回滚](migration.json)：由固定旧工具生成三类 schema 1 合成夹具，不称历史实书重验。
- [完整工程检查](verification.json)：Intel macOS／Python 3.12 执行 397 项测试，390 项通过、7 项按条件跳过、零失败或错误；12 项整包检查全部通过，包含七技能官方校验、实际安装、中文稿与长篇流程回放、文件哈希及文档链接。
- [百万／千万字容量复验](scaling.json)：400／4,000 章、2,000／20,000 张卡片，strict／local 四种组合通过；为合成容量检查，不代表连续生成文学质量。
- [重新测量的静态指令成本](tokens.md) 与 [逐文件哈希](tokens.json)。
- [历史结果基线](prior-results.json) 固定发布开始前的 696 份结果文件，供收尾核对；历史报告里的“尚未发布”描述保留当时含义。

远端分发检查在完成后追加链接与结果。分析专项原稿与评阅保留在原目录：[开发评估汇总](../../../docs/作品深读与评估.md)。测试通过、数据覆盖和文学判断分别解释，不互相替代。
