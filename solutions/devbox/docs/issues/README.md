# 问题记录索引（issues/）

> 维护人：zeek.zhao · 更新：2026-11-28

问题记录按 R 编号登记于过程文档 `../03-风险登记.md`（RK-001，含现状与闭环状态）；本目录存放**独立成篇的排障报告**与后续新增问题记录。

## 已闭环重大问题速查（详见 RK-001 / 对应 TD）

| 编号 | 主题 | 结论 |
|---|---|---|
| R10 | 企业 TLS 网关重签→容器证书校验失败 | http bootstrap→CA→https 顺序（build.sh CA 注入） |
| R11 | GitHub Push Protection 拦截密钥占位符 | filter-branch 全历史重写；入库文本禁带密钥类占位符 |
| R12 | CI 自迭代缺陷链（filebrowser/users import 等） | TD-002 七轮闭环 |
| R13 | magpie XHR 绝对路径 404 | Caddy @magpie_api Referer 分流（D16） |
| R14 | /v1 反代 403 | MAGPIE_TRUST_PROXY=1 |
| R15 | dsh fence Origin 白名单 403 | header_up Origin 同源化（D17） |
| R16 | 插件 pnpm 私有 peer 链断装+magpie 写 API 403 | jq 剔除+--allow-build（D26）；Origin/Referer（D18） |
| R17 | 快照脱敏字面破坏 patch 枚举 | maxTokensField 修正（TD-007） |
| R18 | Tailscale 凭证固化与密钥分离 | age 密文入库/镜像+私钥本地（D29，GD-003 §2） |

## 新增问题记录规范

文件名 `YYYYMMDD-<主题>.md`；内容含：现象/根因/修复/验证/关联提交；登记后在 RK-001 追加 R 编号行。
