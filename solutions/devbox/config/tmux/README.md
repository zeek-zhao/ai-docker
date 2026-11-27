# config/tmux —— tmux 配置说明（PLAN §5.3）

构建期由 Dockerfile config 阶段落地：

1. 克隆 gpakosz/.tmux（oh-my-tmux）→ `/etc/skel/.tmux.conf` + `.tmux.conf.local`
2. 克隆 tpm / tmux-resurrect / tmux-continuum → `/etc/skel/.tmux/plugins/`
3. 在 `.tmux.conf.local` 尾部追加 resurrect/continuum 插件项与 `@continuum-restore on`

会话保存/恢复即开即用；个性化改动建议放 `~/.tmux.conf.local`（age 可还原）。
