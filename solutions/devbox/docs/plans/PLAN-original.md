# ZeekDevAI Container —— 全栈随身开发容器方案

> 项目代号：**zeek-ai-devbox**
> 本地工程 / 挂载目录：**`devbox/`**
> 形态：多阶段分层构建的单容器开发环境，单对外端口统一反代，SSH + Web 终端 + 文件共享 + 导航首页开箱即用。

---

## 1. 方案概览

一个基于 Ubuntu 24.04 的自包含开发容器，内置 C/C++、前端（NVM/Node/pnpm/vite）、Go、ZSH(Oh My Zsh)、Vim(LSP 预配置)、tmux 成熟配置，并通过 Caddy 在**单个对外端口**上按路径反向代理：导航首页、Web 终端（ttyd）、文件共享、远程桌面等服务。

- **构建策略**：多阶段（multi-stage）分层镜像，编译/下载阶段只把成品二进制与配置拷入最终镜像，剥离编译工具链以控制体积。
- **运行策略**：启动脚本自动对齐本地 UID/GID、按 age 私钥 + 清单（manifest）解密还原加密配置、设置账号密码、拉起反代与各服务。
- **数据策略**：只挂载指定的 `devbox/` 数据目录，Docker socket 按需挂载（建议只读），不触碰其他本地路径。
- **鉴权策略**：反代统一采用**登录态会话**（Cookie/Session），登录一次后各子服务免重复认证。

### 1.1 整体架构（文字版）

```
┌──────────────────────────────────────────────────────────────┐
│                      宿主机 (本地 / 服务器)                     │
│   ┌─────────────── devbox/ (唯一挂载数据目录) ───────────────┐ │
│   │  代码 · 配置 · 加密密钥(age 私钥) · HomePage 链接       │ │
│   └───────────────────────────────────────────────────────┘ │
│                 ▲  bind mount 仅此目录；Docker socket 只读    │
└─────────────────│─────────────────────────────────────────────┘
                  │
┌─────────────────│─────────────────────────────────────────────┐
│            ZeekDevAI Container (Ubuntu 24.04)                  │
│                                                                  │
│  Caddy (单端口 :8080, 路径反代 + 统一登录态会话鉴权)             │
│   ├── /            → HomePage 导航首页                          │
│   ├── /term        → ttyd Web 终端                              │
│   ├── /file-share  → filebrowser 文件共享(浏览/上传/删除 devbox) │
│   ├── /dsh         → DSH 网关 127.0.0.1:3081(本体 3080 内网)   │
│   └── /magpie      → Magpie 面板 127.0.0.1:3430(网关 3425)      │
│                                                                  │
│  SSH :22 (映射 2222) ───────────► 本地 SSH 登录                 │
│  Tailscale 用户态模式(无特权端口冲突)                            │
│                                                                  │
│  工具链: C/C++(gcc/g++/cmake/gdb) · NVM/Node · pnpm/vite        │
│          · Go(goproxy.cn) · rg                                   │
│  环境配置: Oh My Zsh(powerlevel10k) · LazyVim · oh-my-tmux      │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 镜像分层设计（多阶段构建）

分层目标：**便于单独更新某一类组件**，同时**编译产物瘦身**——编译阶段携带工具链，最终镜像只保留可运行成品。

| 阶段 | Dockerfile Stage | 职责 | 是否进入最终镜像 |
|------|------------------|------|------------------|
| 0 | `base` | Ubuntu 24.04 + 国内 apt 源 + 系统基础工具 + UTF-8 编码 + 全局 Git 预设 | 是（基础层） |
| 1 | `toolchain-build` | 下载/编译语言工具链：C/C++ 构建链、NVM/Node LTS、pnpm、vite、Go 及 Go 工具链、ripgrep 二进制 | C/C++ 编译器随开发工具进入 final；其余仅 `COPY` 成品 |
| 2 | `config` | Oh My Zsh 及插件、Vim LSP 预配置发行版、tmux 成熟配置、shell 主题与快捷键 | 是（配置层，可独立换） |
| 3 | `services` | ttyd、filebrowser、Caddy、HomePage、Tailscale(用户态)、DSH 等服务二进制 | 是（服务层） |
| 4 | `final` | 合并以上各层成品，写入启动入口脚本 `entrypoint.sh`，清理编译缓存与临时文件 | 最终产出镜像 |

### 2.1 瘦身策略

- 编译/下载在 `toolchain-build` 完成，`final` 只 `COPY --from=` 二进制、全局包与配置；不带 `build-essential`、源码包、编译中间产物。
- 每层结尾 `apt clean` / `rm -rf /var/lib/apt/lists/*`；清理 npm/pnpm/go 缓存。
- 语言工具链只装指定 LTS 版本，不保留多版本残留（NVM 除外，按需可切换）。
- 服务以官方静态二进制或精简镜像提供，避免在最终镜像内做源码编译。

---

## 3. 基础环境（base 层）

### 3.1 系统基座

- 基础镜像：`ubuntu:24.04`
- apt 更换为国内镜像源（默认阿里云/清华源，可配置）
- 区域与编码：`zh_CN.UTF-8` / `en_US.UTF-8`，全局 `LANG=zh_CN.UTF-8`，所有开发路径均使用安全 UTF-8
- 时区：`Asia/Shanghai`

### 3.2 系统工具清单

| 类别 | 组件 |
|------|------|
| 网络 | curl、wget、ca-certificates、openssh-server、sudo |
| 文本/检索 | vim、ripgrep(rg)、less、tree、htop、unzip、zip |
| C/C++ 构建链 | build-essential、gcc、g++、make、cmake、ninja-build、gdb、pkg-config、clang(可选) |
| 安全 | age（加密/解密）、openssl |
| 交互 | zsh、tmux、bash-completion、locales |

> C/C++ 编译器与调试器需要在最终开发镜像内保留（日常编译调试用）；仅中间编译产物、源码缓存留在 `toolchain-build` 层做瘦身。

### 3.3 Git 全局预设（写入 `/etc/gitconfig` 或开发用户 `~/.gitconfig`）

```ini
[user]
    name = zeek.zhao
    email = zeek.zhao@foxmail.com
[core]
    editor = vim
    autocrlf = input
[init]
    defaultBranch = main
```

- 配置国内 Git/Release 镜像加速（如 ghproxy 前缀，可配置开关）。
- 默认编辑器锁定为 **vim**。

---

## 4. 开发工具链（toolchain-build 层）

### 4.1 C / C++

- 构建链：gcc、g++、make、cmake、ninja-build；调试器 gdb；`pkg-config` 管理库依赖；clang/llvm 作为可选补充。
- **预置常用开发库头文件**（默认安装，可在清单里裁剪）：
  - 网络/加密：`libssl-dev`、`libcurl4-openssl-dev`
  - 压缩/数据：`zlib1g-dev`、`libbz2-dev`、`libsqlite3-dev`
  - 文本/序列化：`libxml2-dev`、`libyaml-dev`
  - 基础：`build-essential`、`pkg-config`
  - 可选重型库：`libboost-dev`、Qt5/Qt6 开发包（默认不装，按需开启，避免镜像膨胀）
- 标准 C++ 标准版本对齐当前稳定工具链，支持 C++17/20 编译。

### 4.2 前端

- **NVM**：安装并配置国内 Node 镜像（`NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node`）。
- **Node LTS**：预装一个 LTS 版本，默认启用。
- **包管理 / 常用工具**：pnpm（国内 registry）、vite、yarn（可选）；npm 源指向 npmmirror。
- 全局预装常用通用前端包：TypeScript、tsx、ESLint、Prettier、webpack/vite 相关脚手架等（清单集中在配置文件，便于增删）。

### 4.3 Go

- 安装指定稳定版 Go，GOPROXY 指向国内代理（`https://goproxy.cn,direct`），GOPATH/GOBIN 规范落位。
- 预装常用通用 Go 工具链：staticcheck、dlv（delve 调试器）、golangci-lint、goimports、gopls（LSP）等（清单集中管理）。

### 4.4 检索与格式

- ripgrep 默认按 Unix 风格输出；全局 UTF-8 编码，路径安全处理。

---

## 5. 交互环境配置（config 层）

### 5.1 ZSH + Oh My Zsh

- 安装 Oh My Zsh，默认 shell 切换为 zsh。
- 预装常用插件：`git`、`z`（目录跳转）、`zsh-autosuggestions`、`zsh-syntax-highlighting`、`sudo`、`command-not-found`、`fzf`（可增删）。
- 主题采用功能丰富的 **powerlevel10k**（信息量大、可定制提示符），同步预装配套 Nerd Font 字体；首次进入可用 `p10k configure` 重新向导。

### 5.2 Vim（LSP 预配置）

- 采用主流预配置发行版（默认 **LazyVim**，可切换 AstroNvim），开箱带 LSP、补全、文件检索。
- 集成：`ripgrep` 后端、`telescope.nvim`、`lspconfig`、常用语法与调试插件。
- 与全局默认编辑器 vim 联动。

### 5.3 tmux

- 套用开源成熟配置（默认 oh-my-tmux 风格），预装会话保存/恢复类插件（`tmux-resurrect`、`tmux-continuum`）、基础键位与状态栏优化。

---

## 6. 服务与网络（services 层）

### 6.1 统一反代（Caddy，单对外端口）

- 默认对外 Web 端口 **`8080`**、SSH 映射 **`2222:22`**；两者均通过环境变量 / compose 参数覆盖，镜像内默认值先按此设定。
- 路径路由表：

| 路径 | 后端服务（容器内 loopback） | 说明 |
|------|----------|------|
| `/` | HomePage | 导航首页，**聚合所有本容器对外服务入口**，不配置外部链接 |
| `/term` | ttyd | Web 终端（用户态会话，**禁止 root 登录**） |
| `/file-share` | filebrowser | 浏览 / 上传 / 删除挂载的 `devbox/` 目录 |
| `/dsh` | DSH 网关 `127.0.0.1:3081` | 远程桌面；本体 `127.0.0.1:3080` 不对外 |
| `/magpie` | Magpie 面板 `127.0.0.1:3430` | AI 模型网关面板；网关 API `127.0.0.1:3425` |

- **统一登录态会话鉴权**：反代层维护一套登录态（Cookie/Session），账号复用开发用户 `dev`；登录一次后 HomePage、ttyd、文件共享等子服务共享会话、免重复登录；未登录访问任意路径先跳登录页。会话有效期默认 7 天（可配置）。
- ttyd 以普通开发用户身份启动，不提供 root 会话。
- 所有内部后端只绑 `127.0.0.1`，仅经 Caddy 单端口对外；WebSocket 流量在反代层透传（ttyd / DSH 依赖）。

### 6.2 文件共享

- 使用轻量成熟的 filebrowser（或等价静态文件服务），根目录绑定挂载的 `devbox/`。
- 默认开放**网页目录浏览、下载、上传、新建目录、删除/重命名**等写操作；写权限可通过配置开关收紧为只读。

### 6.3 SSH

- 内置 `openssh-server`，对外暴露 22 端口；本地可直接 `ssh` 进入容器。
- 账号密码见第 7 节；鉴权方式支持密码登录，可追加公钥登录。

### 6.4 Tailscale

- 以**用户态模式**运行，避免特权端口/能力冲突；不依赖宿主内核 TUN。
- 接入配置通过 age 解密后的环境变量或配置文件注入。

### 6.5 服务清单（可插拔）

HomePage、ttyd、filebrowser、Caddy、Tailscale、DSH、Magpie 均为服务层独立组件，可在不改动 base/toolchain 层的前提下单独升级或摘除。

### 6.6 DSH 与 Magpie 接入推荐（默认值）

#### DSH 远程桌面（dshgo / remote-access 形态）

- **端口布局**：DSH Web 本体只监听 `127.0.0.1:3080`，**绝不直接对外**；由远程访问网关监听 `127.0.0.1:3081`，Caddy 经 `/dsh` 反代到 3081。
- **认证方式**：优先复用反代统一登录态；DSH 侧可再设一道访问码（accessCode，4–12 位）或 token 换取的 HttpOnly SameSite 会话 Cookie；开启 CIDR 白名单与失败登录限流，必要时用设备审批模式。
- **网络要求**：反代需透传 WebSocket；控制类路由保持 loopback-only，不经过公开代理。
- **配置注入**：访问码 / token 由 age 解密后的环境变量或配置文件提供，不写明文。

#### Magpie AI 模型网关

- **端口布局**：网关 API 监听 `127.0.0.1:3425`；管理面板监听 `127.0.0.1:3430`；Caddy 经 `/magpie` 反代到面板 3430，网关 API 不直接对外暴露。
- **认证方式**：面板用 `MAGPIE_WEB_KEY` 鉴权（未登录返回 401，访问带 `?k=<key>` 或由反代统一会话带入）；对外调用网关 API 时使用每设备独立的网关密钥。
- **配置注入**：`MAGPIE_WEB_KEY`、供应商 API Key 等敏感项经 age 解密注入，权限 `0600`。
- **可配置项**：端口可用 `MAGPIE_PORT` / 面板端口环境变量覆盖；若暂不接入，预留 `/magpie` 路径与启停开关，不影响其余服务。

> 以上为基于常见自托管形态的推荐默认值；后端地址、端口、密钥均可在配置文件 / 环境变量中调整，后续接入真实实例时按实际部署覆盖。

---

## 7. 账号、权限与启动流程

### 7.1 账号与密码（本地测试默认值）

| 账号 | 密码 | 用途 |
|------|------|------|
| 普通开发用户 `dev`（UID/GID 启动时对齐本地） | `123` | SSH、ttyd、Web 反代登录态、日常开发（Web 登录复用此账号，不另设管理员） |
| `root` | `root` | 容器内提权（谨慎使用） |

> ⚠️ 以上为**本地测试弱密码**；一旦暴露到公网，必须改为强密码并关闭 root/密码直登。

### 7.2 启动脚本 `entrypoint.sh` 执行顺序

1. **对齐权限**：读取传入的本地 `UID` / `GID`，创建或调整开发用户 `dev` 的属主与属组，确保挂载目录读写一致。
2. **设置密码**：强制写入 `dev` 密码 `123`、`root` 密码 `root`（可被环境变量覆盖）。
3. **解密还原配置**：读取加密包内的清单（manifest），用挂载进来的 age 私钥逐项解密，按原始相对路径还原到对应目录（如 `~/.ssh/`、`~/.gitconfig` 及其他指定目录/单文件）。
4. **准备目录**：确保 `devbox/` 挂载点、HomePage、文件共享根目录权限正确。
5. **拉起服务**：依次启动 SSH、Tailscale(用户态)、各内部服务，最后由 Caddy 按路径统一反代。
6. **前台守护**：主进程守护容器退出，日志汇聚到 stdout。

### 7.3 挂载与隔离

- 仅挂载指定的 `devbox/` 数据目录到容器内对应工作目录。
- Docker socket：按需挂载，**默认只读**；不挂载其他本地路径。
- 开发用户家目录与配置落在用户卷内，避免污染镜像层。

---

## 8. 配置加密、打包与按目录还原（age + 配套脚本）

### 8.1 加密算法

- 采用 **age**（现代高性能对称友好的公钥加密，轻量、无传统 RSA 庞大密钥对）作为最高等级加密方案。
- 本地持**公钥**加密；容器启动只挂载对应**私钥**（或经环境变量注入）。私钥严禁打入镜像、严禁提交版本库。

### 8.2 加密对象（目录级 / 文件级）

脚本同时支持两类对象，由清单声明，还原时按原始结构落位：

| 对象类型 | 示例 | 打包方式 | 还原方式 |
|----------|------|----------|----------|
| 整个目录 | `~/.ssh/`、Git 相关配置目录、其他配置目录 | 先按相对路径打成 `tar` 包，再 age 加密为 `.age` | 解密后解包到目标目录，保留目录结构与权限 |
| 单个文件 | `~/.gitconfig`、某个 `config`/`.env`/Token 文件 | 直接 age 加密为 `.age` | 解密后写回目标路径并恢复权限 |

### 8.3 配套脚本（随加密包一起打包）

脚本与被加密的配置**打包在同一个加密发布包内**，解包后即可在目标环境直接使用，不依赖外部副本。

| 脚本 | 职责 | 运行位置 |
|------|------|----------|
| `scripts/age-keygen.sh` | 生成 / 校验 age 密钥对；提示公钥入库、私钥本地保存 | 本地一次性 |
| `scripts/encrypt.sh` | 读取清单，对公钥加密目录（先 tar）/ 文件，产出 `.age` 与更新后的 manifest | 本地 |
| `scripts/pack.sh` | 把加密产物、manifest、解密/还原脚本打成一个发布包（`devbox-secrets.tar.age` 或目录包） | 本地 |
| `scripts/decrypt.sh` | 容器内：按 manifest 用私钥解密，目录解包/单文件写回，恢复属主与权限 | 容器启动 |
| `scripts/restore.sh` | 封装"解密 + 按目录还原 + 权限修复"流程，供 `entrypoint.sh` 调用；支持 dry-run 与指定还原根目录 | 容器启动 |

### 8.4 清单（manifest）格式

`manifest.json`（或 YAML）逐条声明加密项，记录类型、源路径、目标还原路径、权限与注释：

```json
{
  "version": "1",
  "entries": [
    {
      "type": "dir",
      "source": ".ssh",
      "target": "~/.ssh",
      "mode": "0700",
      "encrypted": "ssh.tar.age",
      "note": "SSH 私钥与 known_hosts"
    },
    {
      "type": "file",
      "source": ".gitconfig",
      "target": "~/.gitconfig",
      "mode": "0600",
      "encrypted": "gitconfig.age",
      "note": "Git 身份与别名配置"
    },
    {
      "type": "file",
      "source": "env/tokens.env",
      "target": "~/.config/devbox/tokens.env",
      "mode": "0600",
      "encrypted": "tokens.env.age"
    }
  ]
}
```

- `source` 为本地相对打包根的路径；`target` 为容器内还原目标（支持 `~` 展开到开发用户家目录）。
- 目录条目保留内部层级；文件条目原样落位。
- 还原后按 `mode` 与 UID/GID 修复权限，敏感目录/文件默认 `0700`/`0600`。

### 8.5 完整流程

1. **本地建包**：`age-keygen.sh` 生成密钥 → 编辑 `manifest` 纳入要加密的目录/文件 → `encrypt.sh` 用公钥逐项加密 → `pack.sh` 将 `.age` 产物、`manifest`、`decrypt.sh`/`restore.sh` 打成单一发布包。
2. **入库 / 分发**：发布包与公钥可入库；私钥只在本机或受控密钥管理处保存。
3. **容器启动还原**：`entrypoint.sh` 调 `restore.sh`，读 manifest → 私钥解密 → 目录解包 / 文件写回 → 修复属主与权限；明文仅落在运行时家目录，不持久化到镜像层。
4. **增量更新**：增删配置项只改 `manifest` 并重新 `encrypt.sh` + `pack.sh`；轮换密钥时重新加密全包。

### 8.6 安全约束

- 私钥不进镜像、不进仓库；发布包内只含公钥可加密的密文与还原脚本。
- 解密出的敏感文件在镜像构建阶段不出现；运行结束可按策略清理明文临时文件。
- 脚本对路径做越权校验：还原目标不允许逃逸到清单声明目录之外。

---

## 9. 工程目录结构（落地形态）

```
devbox/
├── PLAN.md                     # 本方案文档
├── Dockerfile                  # 多阶段分层构建文件
├── docker-compose.yml          # 一键编排(端口/UID/GID 等参数化)
├── entrypoint.sh               # 启动入口: 权限对齐/密码/解密还原/起服务
├── config/
│   ├── gitconfig               # Git 身份预设
│   ├── zsh/                    # Oh My Zsh + powerlevel10k 配置
│   ├── vim/                    # LazyVim 配置
│   ├── tmux/                   # tmux 成熟配置
│   ├── caddy/                  # 反代路由 + 登录态会话鉴权配置
│   └── homepage/               # HomePage 导航链接清单
├── secrets/
│   ├── manifest.json           # 加密条目清单(目录/文件/目标路径/权限)
│   ├── *.age                   # age 加密后的目录包/单文件(入库)
│   ├── devbox-secrets.tar.age  # pack.sh 产出的单一加密发布包
│   └── README.md               # 密钥与加解密流程说明(私钥不入库)
├── data/                       # 运行时挂载数据目录(代码/文件共享根)
└── scripts/
    ├── build.sh                # 分层构建脚本
    ├── run.sh                  # 启动/挂载/端口映射示例(参数化)
    ├── age-keygen.sh           # 生成/校验 age 密钥对
    ├── encrypt.sh              # 按 manifest 本地加密目录/文件
    ├── pack.sh                 # 打包密文 + 清单 + 还原脚本为发布包
    ├── decrypt.sh              # 容器内按清单解密
    └── restore.sh              # 解密 + 按目录还原 + 权限修复
```

---

## 10. 构建与使用（示例命令）

### 10.1 构建

```bash
# 分层构建，可指定目标阶段便于单独调试
docker build --target final -t zeek-ai-devbox:latest .
```

### 10.2 启动（示例）

```bash
docker run -d \
  --name zeek-devbox \
  -p 8080:8080 \
  -p 2222:22 \
  -e HOST_UID=$(id -u) \
  -e HOST_GID=$(id -g) \
  -v "$PWD/data:/home/dev/data" \
  -v "$PWD/secrets/key.txt:/secrets/key.txt:ro" \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  zeek-ai-devbox:latest
```

### 10.3 访问

- Web 导航 / 终端 / 文件共享：`http://<host>:8080/`
- SSH：`ssh -p 2222 dev@<host>`（密码 `123`）

---

## 11. 默认值与可配置项

| 项 | 默认值 | 说明 |
|----|--------|------|
| 对外 Web 端口 | `8080` | 环境变量 / compose 参数覆盖 |
| SSH 端口映射 | `2222:22` | 避免与宿主 22 冲突，可参数化 |
| 反代鉴权方式 | 登录态会话（Cookie/Session），账号复用 `dev` | 一次登录，子服务共享；会话默认 7 天 |
| HomePage | 聚合本容器全部对外服务入口 | 不配置外部链接 |
| Vim 发行版 | LazyVim | 可切 AstroNvim |
| ZSH 主题 | powerlevel10k（含 Nerd Font） | 可在 `p10k configure` 重配 |
| 前端 registry | npmmirror | 可配 |
| Go 代理 | goproxy.cn | 可配 |
| C/C++ 工具链 | gcc/g++/make/cmake/ninja/gdb + 常用开发库 | 重型库（Boost/Qt）按需开启 |
| DSH | 本体 `127.0.0.1:3080`，网关 `127.0.0.1:3081`，`/dsh` 反代 | accessCode / 会话 Cookie + CIDR 白名单 |
| Magpie | 网关 `127.0.0.1:3425`，面板 `127.0.0.1:3430`，`/magpie` 反代 | `MAGPIE_WEB_KEY` 鉴权，密钥 age 注入 |
| 文件共享权限 | 浏览 + 下载 + 上传 + 删除 | 可开关收紧为只读 |
| 普通用户密码 / root 密码 | `123` / `root` | 测试用，公网必改 |

---

## 12. 风险与注意事项

1. **弱密码仅限内网/本地测试**；公网部署前必须替换强密码、禁用 root 直登、收紧文件共享写权限。
2. **Docker socket 只读挂载**仍有提权面，仅在可信环境开启；不需要容器操控本地 Docker 时不要挂载。
3. **age 私钥**严禁打入镜像或提交仓库；轮换密钥需重新加密 `secrets/*.age`。
4. **Tailscale 用户态模式**功能受限（部分组网/子网路由能力依赖内核态），按需评估。
5. 国内镜像源地址会变动，方案中以变量集中管理，便于失效后切换。

---

## 13. 最终确认结论

### 13.1 已全部拍板

- **Web 登录账号**：复用开发用户 `dev`，不另设管理员；会话有效期默认 7 天（可配）。
- **C/C++ 预制库**：预置网络/加密/压缩/数据/文本类常用开发库；Boost、Qt 等重型库默认不装，按需开启。
- **HomePage**：聚合本容器全部对外可访问服务入口，**不配置外部链接**。
- **反代鉴权**：登录态会话（Cookie/Session），一次登录共享到各子服务。
- **文件共享**：开放浏览 / 下载 / 上传 / 新建目录 / 删除 / 重命名，可开关收紧为只读。
- **前端 / Go 工具链**：安装常用通用包，清单集中配置便于增删。
- **ZSH 主题**：powerlevel10k，配套 Nerd Font。
- **端口**：默认 Web `8080`、SSH `2222:22`，全部参数化，可在启动参数 / compose 覆盖。
- **加密**：配套加密 / 打包 / 解密 / 按目录还原脚本，与密文、清单打成同一发布包。

### 13.2 DSH / Magpie 推荐接入（已写入 6.6）

- **DSH**：本体 `127.0.0.1:3080` 不对外，网关 `127.0.0.1:3081`，`/dsh` 反代；accessCode 或会话 Cookie + CIDR 白名单 + 失败限流，WebSocket 透传。
- **Magpie**：网关 API `127.0.0.1:3425`，面板 `127.0.0.1:3430`，`/magpie` 反代；`MAGPIE_WEB_KEY` 鉴权，密钥经 age 解密注入；暂不接入时预留路径与启停开关。

> 主体结构、默认值与接入方式已闭环，可据此生成 `Dockerfile`、`entrypoint.sh`、加解密脚本与各配置文件的可执行工程。

> （注：部分内容由豆包 AI 生成）