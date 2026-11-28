功能: 漂移检测器 detect_drift（阶段 3，FR-D1，docs/01 §12.2）
  以 out/inventory.json 唯一真相表为输入，对每个仓库只比 sha 不下载内容：
  上游真实 HEAD sha（GitHub API，受请求预算约束）vs mirror 侧 ls-remote
  HEAD sha（git 协议只读远端引用，不占 API 配额）。不一致则产出
  drift_detected 事件（白名单唯一出处 config/policy.yaml），并把观测到的
  mirror sha 写回记录 mirror_sha。测试通过注入假 fetcher/prober 覆盖行为，
  禁止真实网络调用（AGENTS §3.4）。

@SC-M6-01
场景: 清单与 mirror 全部一致时不产生漂移事件且写回观测 sha
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main
并且 清单中 "acme/b" 的 head_sha 为 bbb222 分支 main mirror_sha aaa111
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 上游 "acme/b" 的真实 HEAD 为 bbb222
并且 mirror 侧 "acme/a" 的 HEAD 为 aaa111
并且 mirror 侧 "acme/b" 的 HEAD 为 bbb222
当 执行漂移检测 请求上限为 10
那么 漂移事件数为 0
而且 清单记录 2 条 且消耗请求 2 次
而且 记录 "acme/a" 写回 mirror_sha aaa111
而且 记录 "acme/a" 保留 head_sha aaa111

@SC-M6-02
场景: 上游未变而 mirror 回退一个提交时报漂移（FR-D1 验收）
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main mirror_sha aaa111
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 mirror 侧 "acme/a" 的 HEAD 为 ccc000
当 执行漂移检测 请求上限为 10
那么 漂移事件数为 1
而且 事件 kind 为 drift_detected
而且 事件 subject 为 "acme/a"
而且 事件 summary 包含 "repo sync --force-sync"
而且 记录 "acme/a" 写回 mirror_sha ccc000
而且 记录 "acme/a" 保留 head_sha aaa111

@SC-M6-03
场景: mirror 领先上游同样判定漂移（只比 sha 不比方向）
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 mirror 侧 "acme/a" 的 HEAD 为 ddd999
当 执行漂移检测 请求上限为 10
那么 漂移事件数为 1
而且 事件 subject 为 "acme/a"
而且 记录 "acme/a" 写回 mirror_sha ddd999

@SC-M6-04
场景: 请求预算耗尽时保存游标续跑且未检仓库原样随行
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main
并且 清单中 "acme/b" 的 head_sha 为 bbb222 分支 main
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 上游 "acme/b" 的真实 HEAD 为 bbb222
并且 mirror 侧 "acme/a" 的 HEAD 为 aaa111
并且 mirror 侧 "acme/b" 的 HEAD 为 bbb222
当 执行漂移检测 请求上限为 1
那么 检测未完成
而且 漂移游标剩余 [acme/b]
而且 清单记录 2 条 且消耗请求 1 次
而且 记录 "acme/b" 保留 head_sha bbb222

@SC-M6-05
场景: 漂移事件通过 config 告警白名单构建 payload（策略唯一来源）
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 mirror 侧 "acme/a" 的 HEAD 为 ccc000
当 执行漂移检测 请求上限为 10
那么 事件通过告警白名单构建 payload 成功
而且 事件 payload dedup_key 为 drift_detected:acme/a
而且 事件 payload channels 为 [github-issue, feishu-webhook]

@SC-M6-06
场景: mirror 探测走 git 协议不消耗请求预算（IF-2）
假如 清单中 "acme/a" 的 head_sha 为 aaa111 分支 main
并且 上游 "acme/a" 的真实 HEAD 为 aaa111
并且 mirror 侧 "acme/a" 的 HEAD 为 aaa111
当 执行漂移检测 请求上限为 10
那么 清单记录 1 条 且消耗请求 1 次
而且 mirror 探测共 1 次
