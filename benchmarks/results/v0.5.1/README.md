# v0.5.1 发布验证

v0.5.1 已于 2026-09-10 19:04:42（北京时间）发布。此目录保存本版重新执行的发布检查，不覆盖历史回执。逐项分发状态见 [发布状态](release/state.json)，功能、兼容和平台范围见 [版本说明](../../../docs/releases/v0.5.1.md)。

- [ZIP 构建](package.json)：七个技能、33 个载荷文件，SHA-256 与此前最后一次分析试用的技能快照一致。
- [npm 构建](npm-package.json)：技能载荷与 ZIP 绑定，新增本版平台提示，历史 wrapper 保持原字节。准备时缺少校验文件、npm 不在路径及现有 npm 启动器路径不匹配的三次失败分别保存在 npm-package-first-failed.json、npm-package-second-failed.json、npm-package-third-failed.json；随后使用现有 npm 的 JS 入口完成构建。
- [v0.5.0→v0.5.1 整套升级](upgrade.json)：在隔离工程验证新版文件、旧版备份、重复升级和小说保护。
- [旧库迁移与回滚](migration.json)：由固定旧工具生成三类 schema 1 合成夹具，不称历史实书重验。
- [完整工程检查](verification.json)：Intel macOS／Python 3.12 执行 397 项测试，390 项通过、7 项按条件跳过、零失败或错误；12 项整包检查全部通过，包含七技能官方校验、实际安装、中文稿与长篇流程回放、文件哈希及文档链接。
- [百万／千万字容量复验](scaling.json)：400／4,000 章、2,000／20,000 张卡片，strict／local 四种组合通过；为合成容量检查，不代表连续生成文学质量。
- [重新测量的静态指令成本](tokens.md) 与 [逐文件哈希](tokens.json)。
- [历史结果基线](prior-results.json) 固定发布开始前的 696 份结果文件，供收尾核对；历史报告里的“尚未发布”描述保留当时含义。

- [固定标签](release/tag.json) 对应 `4fd53f80e26efc0eadda50b62edaf34a046d363a`，后续文档提交不移动该标签。
- [远端 CI](release/ci.json)：Linux 397 项中 385 通过、12 平台跳过，全部步骤成功；Windows 8 项中 7 通过、1 项已知导出失败后停止，仍使用 v0.4.0。[完整原始日志](release/ci-log.txt)。
- [Release 回下载](release/release.json) 与 [官方固定标签隔离安装](release/remote-install.json)：7 个技能、33 文件完全一致，四项 CLI 检查通过，临时数据已清理。
- [公开 Packages 发布与注册表下载](release/packages.json) 及 [工作流](release/packages-workflow.json)：33 个载荷与 2 个包装文件匹配；[回下载后的本机独立复核](release/package-check.json) 核对文件、实际 SHA-512，并重跑四项 CLI。
- [发布收尾核对](release/final-check.json)：696 份历史结果原字节未变，发布代码和测试快照未变，当前全局技能与 33 文件发布载荷一致，文档链接有效，临时工具已清理。

分析专项原稿与评阅保留在原目录：[开发评估汇总](../../../docs/作品深读与评估.md)。测试通过、数据覆盖和文学判断分别解释，不互相替代。
