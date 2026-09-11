# v0.5.2 发布验证

本目录保存 v0.5.2 的独立发布验证，不复用旧版数字冒充新测量。当前正在准备发布；功能与兼容范围见 [版本说明](../../../docs/releases/v0.5.2.md)。

- [ZIP 构建](package.json)：七个技能、33 个载荷文件。
- [npm 构建](npm-package.json)：载荷与 ZIP 一致；保留旧版包装内容，v0.5.2 明确 macOS/Linux 范围与 Windows 已知限制。
- [v0.5.1→v0.5.2 升级](upgrade.json)：隔离项目的整套更新、旧版保留与重复升级检查。
- [旧库迁移](migration.json)：固定旧工具生成的三类 schema 1 合成夹具，不代表历史实书重验。
- [静态指令成本](tokens.md) 与 [文件哈希](tokens.json)：重新计数，不是实际账户用量或文学质量证据。
- [百万／千万字合成容量](scaling.json)：400／4,000 章、2,000／20,000 张卡，strict／local 四组合通过；不是持续创作或文学质量验证。
- [历史结果基线](prior-results.json)：发布开始前保存的旧回执哈希，收尾核对原字节不变。

[完整工程检查](verification.json) 已通过：本机 Intel macOS／Python 3.12 运行443项测试，436通过、7项按条件跳过、零失败，12项整包检查通过。远端 CI、Release 回下载、官方固定标签安装及 Packages 结果完成后逐项补入本页。Windows 的已知正文/报告导出问题没有纳入本次修复，不声明全平台通过。
