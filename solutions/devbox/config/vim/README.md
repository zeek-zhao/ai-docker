# config/vim —— Vim/Neovim 预配置说明（PLAN §5.2）

本工程不携带完整 LazyVim 配置副本，构建期由 Dockerfile config 阶段克隆
LazyVim 官方 starter 至 `/etc/skel/.config/nvim`（首启 nvim 自动引导插件）。

- 发行版：LazyVim（默认；可切 AstroNvim，改 Dockerfile `LAZYVIM_STARTER_REPO`）
- 检索后端：ripgrep（base 层已装）；telescope/lspconfig 由 starter 预置
- 首次启动需联网拉取插件；如需离线缓存，在构建机执行一次
  `nvim --headless "+Lazy! sync" +qa` 后将 `~/.local/share/nvim` 一并固化。

运行时用户级覆盖：经 age 还原 `~/.config/nvim/`（见 secrets/manifest.json 条目示例）。
