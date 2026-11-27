# syntax=docker/dockerfile:1
# =============================================================================
# Dockerfile —— zeek-ai-devbox 多阶段分层构建
# 文档编号：BD-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 阶段：base → toolchain-build → config → services → final
# 构建：docker build --target final -t zeek-ai-devbox:latest .
# 镜像源均由 ARG 集中管理，失效后一行覆盖切换（PLAN §12.5）
# =============================================================================

# 可按需换基础镜像源，如 docker.m.daocloud.io/library/ubuntu:24.04
ARG BASE_IMAGE=ubuntu:24.04

# -----------------------------------------------------------------------------
# Stage 0: base —— 系统基座：国内源 / UTF-8 / 时区 / 系统工具 / C&C++ 工具链 / Git 预设
# -----------------------------------------------------------------------------
FROM ${BASE_IMAGE} AS base

ARG APT_MIRROR=mirrors.aliyun.com
ARG TIMEZONE=Asia/Shanghai
ARG DEFAULT_LANG=zh_CN.UTF-8
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=${DEFAULT_LANG} \
    TZ=${TIMEZONE}

# 1) apt 国内源（Ubuntu 24.04 使用 deb822 sources；兼容旧格式兜底）
#    bootstrap 阶段用 http：基础镜像尚无 ca-certificates，https 源无法握手；装包后再切 https（见 2.5）
RUN if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
      sed -i "s|http://archive.ubuntu.com|http://${APT_MIRROR}|g; s|http://security.ubuntu.com|http://${APT_MIRROR}|g; s|http://cn.archive.ubuntu.com|http://${APT_MIRROR}|g" /etc/apt/sources.list.d/ubuntu.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://archive.ubuntu.com|http://${APT_MIRROR}|g; s|http://security.ubuntu.com|http://${APT_MIRROR}|g" /etc/apt/sources.list; \
    fi

# 2) 系统工具 + C/C++ 构建链 + 常用开发库（PLAN §3.2 / §4.1；编码与时区 PLAN §3.1）
#    注：ripgrep/age/fzf 经 apt 提供官方打包二进制，等效于 toolchain 下载成品（已在评审记录）
RUN apt-get update && apt-get install -y --no-install-recommends \
      locales tzdata ca-certificates curl wget sudo \
      openssh-server openssh-client \
      vim less tree htop unzip zip ripgrep fzf fontconfig \
      build-essential gcc g++ make cmake ninja-build gdb pkg-config \
      libssl-dev libcurl4-openssl-dev zlib1g-dev libbz2-dev \
      libsqlite3-dev libxml2-dev libyaml-dev \
      zsh tmux bash-completion git age openssl jq \
      procps iproute2 \
 && locale-gen zh_CN.UTF-8 en_US.UTF-8 \
 && update-locale LANG=${DEFAULT_LANG} \
 && ln -fs /usr/share/zoneinfo/${TIMEZONE} /etc/localtime \
 && dpkg-reconfigure -f noninteractive tzdata \
 && apt-get clean && rm -rf /var/lib/apt/lists/*

# 2.5) 企业网私有 CA 注入 + apt 源升级 https（PLAN §12.5 换源指引配套；公网标准环境仅 .gitkeep，等效 no-op）
#      build.sh 构建前将宿主机 /usr/local/share/ca-certificates/*.crt 复制到 .buildctx/ca/；
#      toolchain-build/config/services 阶段经 FROM base 继承信任库，GitHub/镜像站 HTTPS 全通。
COPY .buildctx/ca/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates \
 && if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then \
      sed -i "s|http://${APT_MIRROR}|https://${APT_MIRROR}|g" /etc/apt/sources.list.d/ubuntu.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://${APT_MIRROR}|https://${APT_MIRROR}|g" /etc/apt/sources.list; \
    fi

# 3) Git 全局预设（PLAN §3.3，写入 /etc/gitconfig；运行时可被 age 还原的 ~/.gitconfig 覆盖）
COPY config/gitconfig /etc/gitconfig

# -----------------------------------------------------------------------------
# Stage 1: toolchain-build —— 语言工具链下载/编译（成品入 final，编译工具链不入）
# -----------------------------------------------------------------------------
FROM base AS toolchain-build

ARG GH_PROXY=""
ARG NVM_REPO="https://github.com/nvm-sh/nvm.git"
ARG NVM_VERSION=v0.40.3
ARG NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG GO_VERSION=auto
ARG GO_PROXY=https://goproxy.cn,direct

ENV NVM_DIR=/opt/nvm \
    NVM_NODEJS_ORG_MIRROR=${NVM_NODEJS_ORG_MIRROR} \
    GOBIN=/out/gobin \
    GOPATH=/out/gopath

# 1) NVM + Node LTS + 前端全局工具（PLAN §4.2）
RUN mkdir -p "${NVM_DIR}" \
 && git clone --depth 1 --branch "${NVM_VERSION}" "${GH_PROXY}${NVM_REPO}" "${NVM_DIR}" \
 && . "${NVM_DIR}/nvm.sh" \
 && nvm install --lts \
 && nvm alias default 'lts/*' \
 && npm config set registry "${NPM_REGISTRY}" \
 && npm install -g pnpm yarn typescript tsx eslint prettier vite \
 && npm install -g --allow-scripts=@deepseek-ai/dsh-subprocess-local,koffi,node-pty,protobufjs "@deepseek-ai/dsh@0.2.2-rc.5" \
 && pnpm config set registry "${NPM_REGISTRY}" --global \
 && npm cache clean --force \
 && pnpm store prune

# 2) Go 工具链（auto = 从 go.dev 解析最新稳定版；PLAN §4.3）
RUN set -eux; \
    if [ "${GO_VERSION}" = "auto" ]; then \
      GO_VERSION="$(curl -fsSL 'https://go.dev/dl/?mode=json' | grep -o '"version": *"go[0-9.]*"' | head -1 | grep -o 'go[0-9.]*' | sed 's/^go//')"; \
    fi; \
    curl -fsSL -o /tmp/go.tgz "https://mirrors.aliyun.com/golang/go${GO_VERSION}.linux-amd64.tar.gz" \
 && tar -C /usr/local -xzf /tmp/go.tgz \
 && rm -f /tmp/go.tgz \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

# 3) Go 通用工具链（GOBIN=/out/gobin，成品拷入 final 的 /usr/local/bin）
RUN go env -w GOPROXY="${GO_PROXY}" \
 && go install golang.org/x/tools/cmd/goimports@latest \
 && go install golang.org/x/tools/gopls@latest \
 && go install honnef.co/go/tools/cmd/staticcheck@latest \
 && go install github.com/go-delve/delve/cmd/dlv@latest \
 && go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest \
 && rm -rf /out/gopath/pkg

# 4) auth-gate 会话鉴权微服务（R4 方案，源码在 config/caddy/authgate）
COPY config/caddy/authgate/ /src/authgate/
RUN cd /src/authgate \
 && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/auth-gate . \
 && rm -rf /src/authgate

# 5) Bun（magpie 插件 workspace 依赖管理；restore-notes §0/§2.1）
ARG BUN_VERSION=v1.3.4
RUN curl -fsSL -o /tmp/bun.zip \
      "${GH_PROXY}https://github.com/oven-sh/bun/releases/download/bun-${BUN_VERSION}/bun-linux-x64.zip" \
 && cd /tmp && unzip -q bun.zip && mv bun-linux-x64/bun /usr/local/bin/bun \
 && chmod +x /usr/local/bin/bun && rm -rf /tmp/bun.zip /tmp/bun-linux-x64 \
 && bun --version

# 6) DSH desktop 档案骨架（TD-003/D12：快照结构 + 构建期 pnpm install；凭证零入库）
#    产物 /out/skel-dsh/ → final 拷至 /etc/skel/.dsh/profiles/desktop/（useradd 时 cp -a 落 dev 家目录）
COPY config/dsh/profile-package.json /out/skel-dsh/package.json
COPY config/dsh/cordis.yml config/dsh/cordis.patch.yml /out/skel-dsh/
RUN cd /out/skel-dsh \
 && . "${NVM_DIR}/nvm.sh" && nvm use default >/dev/null \
 && pnpm install --frozen-lockfile=false --prefer-offline 2>&1 | tail -3 \
 && rm -rf node_modules/.cache && pnpm store prune

# 7) Magpie 插件骨架（TD-003/Q3：page-free-tokens 本地 tgz 缺失已剔除，其余 bun install）
#    产物 /out/skel-magpie/ → final 拷至 /etc/skel/.config/magpie/
COPY config/magpie/plugins-package.json /out/skel-magpie/plugins/package.json
COPY config/magpie/plugins.json config/magpie/mcp-hub-servers.json /out/skel-magpie/
RUN cd /out/skel-magpie/plugins \
 && bun install 2>&1 | tail -3

# -----------------------------------------------------------------------------
# Stage 2: config —— 交互环境：Oh My Zsh / powerlevel10k / LazyVim / tmux / 字体
# -----------------------------------------------------------------------------
FROM base AS config

ARG GH_PROXY=""
ARG OMZ_REPO="https://github.com/ohmyzsh/ohmyzsh.git"
ARG P10K_REPO="https://github.com/romkatv/powerlevel10k.git"
ARG ZSH_AUTOSUGGESTIONS_REPO="https://github.com/zsh-users/zsh-autosuggestions.git"
ARG ZSH_SYNTAX_HIGHLIGHTING_REPO="https://github.com/zsh-users/zsh-syntax-highlighting.git"
ARG OH_MY_TMUX_REPO="https://github.com/gpakosz/.tmux.git"
ARG LAZYVIM_STARTER_REPO="https://github.com/LazyVim/starter.git"
ARG LAZYVIM_STARTER_BRANCH=main

# 1) Oh My Zsh（系统级安装至 /usr/share/oh-my-zsh）+ 插件 + powerlevel10k（PLAN §5.1）
RUN git clone --depth 1 "${GH_PROXY}${OMZ_REPO}" /usr/share/oh-my-zsh \
 && git clone --depth 1 "${GH_PROXY}${ZSH_AUTOSUGGESTIONS_REPO}" /usr/share/oh-my-zsh/custom/plugins/zsh-autosuggestions \
 && git clone --depth 1 "${GH_PROXY}${ZSH_SYNTAX_HIGHLIGHTING_REPO}" /usr/share/oh-my-zsh/custom/plugins/zsh-syntax-highlighting \
 && git clone --depth 1 "${GH_PROXY}${P10K_REPO}" /usr/share/oh-my-zsh/custom/themes/powerlevel10k \
 && rm -rf /usr/share/oh-my-zsh/.git /usr/share/oh-my-zsh/custom/plugins/*/.git /usr/share/oh-my-zsh/custom/themes/powerlevel10k/.git

# 2) powerlevel10k 配套 MesloLGS NF 字体（PLAN §5.1；sh 兼容写法，勿用 bash 专属扩展）
RUN mkdir -p /usr/local/share/fonts \
 && curl -fsSL -o "/usr/local/share/fonts/MesloLGS NF Regular.ttf"     "${GH_PROXY}https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Regular.ttf" \
 && curl -fsSL -o "/usr/local/share/fonts/MesloLGS NF Bold.ttf"        "${GH_PROXY}https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Bold.ttf" \
 && curl -fsSL -o "/usr/local/share/fonts/MesloLGS NF Italic.ttf"      "${GH_PROXY}https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Italic.ttf" \
 && curl -fsSL -o "/usr/local/share/fonts/MesloLGS NF Bold Italic.ttf" "${GH_PROXY}https://github.com/romkatv/powerlevel10k-media/raw/master/MesloLGS%20NF%20Bold%20Italic.ttf" \
 && fc-cache -f >/dev/null

# 3) zsh/tmux 用户骨架（首次建用户即生效；.p10k.zsh 由 p10k configure 生成）
COPY config/zsh/zshrc /etc/skel/.zshrc
RUN git clone --depth 1 "${GH_PROXY}${OH_MY_TMUX_REPO}" /tmp/oh-my-tmux \
 && cp /tmp/oh-my-tmux/.tmux.conf /etc/skel/.tmux.conf \
 && cp /tmp/oh-my-tmux/.tmux.conf.local /etc/skel/.tmux.conf.local \
 && rm -rf /tmp/oh-my-tmux \
 && git clone --depth 1 "${GH_PROXY}https://github.com/tmux-plugins/tpm.git" /etc/skel/.tmux/plugins/tpm \
 && git clone --depth 1 "${GH_PROXY}https://github.com/tmux-plugins/tmux-resurrect.git" /etc/skel/.tmux/plugins/tmux-resurrect \
 && git clone --depth 1 "${GH_PROXY}https://github.com/tmux-plugins/tmux-continuum.git" /etc/skel/.tmux/plugins/tmux-continuum \
 && rm -rf /etc/skel/.tmux/plugins/*/.git

# 4) LazyVim 骨架（首次启动 nvim 自动引导插件；PLAN §5.2）
RUN git clone --depth 1 --branch "${LAZYVIM_STARTER_BRANCH}" "${GH_PROXY}${LAZYVIM_STARTER_REPO}" /tmp/lazyvim \
 && rm -rf /etc/skel/.config/nvim \
 && mkdir -p /etc/skel/.config \
 && cp -r /tmp/lazyvim /etc/skel/.config/nvim \
 && rm -rf /etc/skel/.config/nvim/.git /etc/skel/.config/nvim/.github \
 && rm -rf /tmp/lazyvim

# 5) tmux 插件项写入 .tmux.conf.local 尾部（resurrect/continuum）
RUN printf '\n# devbox: 会话保存/恢复插件（PLAN §5.3）\nset -g @plugin "tmux-plugins/tmux-resurrect"\nset -g @plugin "tmux-plugins/tmux-continuum"\nset -g @continuum-restore "on"\n' >> /etc/skel/.tmux.conf.local

# -----------------------------------------------------------------------------
# Stage 3: services —— 服务二进制：ttyd / filebrowser / Caddy / HomePage / Tailscale
# -----------------------------------------------------------------------------
FROM base AS services

ARG GH_PROXY=""
ARG TTYD_VERSION=1.7.7
ARG FILEBROWSER_VERSION=auto
ARG TAILSCALE_VERSION=auto
ARG CADDY_DOWNLOAD_URL="https://caddyserver.com/api/download?os=linux&arch=amd64"
# 注：鉴权由独立 auth-gate + Caddy forward_auth 完成，无需额外 Caddy 模块

RUN set -eux; mkdir -p /out /opt

# 1) ttyd Web 终端（静态二进制）
RUN curl -fsSL -o /out/ttyd \
      "${GH_PROXY}https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" \
 && chmod +x /out/ttyd

# 2) filebrowser 文件共享（auto = GitHub API 最新版）
RUN set -eux; \
    FBV="${FILEBROWSER_VERSION}"; \
    if [ "${FBV}" = "auto" ]; then \
      FBV="$(curl -fsSL https://api.github.com/repos/filebrowser/filebrowser/releases/latest | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)"; \
    fi; \
    curl -fsSL -o /tmp/fb.tar.gz \
      "${GH_PROXY}https://github.com/filebrowser/filebrowser/releases/download/${FBV}/linux-amd64-filebrowser.tar.gz" \
 && tar -C /out -xzf /tmp/fb.tar.gz filebrowser && rm -f /tmp/fb.tar.gz

# 3) Caddy（caddyserver.com 官方在线构建，标准模块）
RUN curl -fsSL -o /out/caddy "${CADDY_DOWNLOAD_URL}" && chmod +x /out/caddy

# 3b) Magpie CLI（订阅池化网关，TD-003/D11：yetone/magpie release 单二进制，headless web+gateway 全功能）
ARG MAGPIE_VERSION=v0.1.4984
RUN curl -fsSL -o /out/magpie \
      "${GH_PROXY}https://github.com/yetone/magpie/releases/download/${MAGPIE_VERSION}/magpie-cli-linux-amd64" \
 && chmod +x /out/magpie

# 4) HomePage —— 已移除发布包下载（gethomepage v1→v2 各 release 均不发布二进制资产，D5 变更）；
#    改由独立阶段 homepage-src 从官方镜像提取，见 final 之前定义。

# 5) Tailscale（用户态；auto = pkgs.tailscale.com stable 最新）
RUN set -eux; \
    TSV="${TAILSCALE_VERSION}"; \
    if [ "${TSV}" = "auto" ]; then \
      TSV="$(curl -fsSL 'https://pkgs.tailscale.com/stable/?mode=json' | grep -o '"Version": *"[^"]*"' | head -1 | cut -d'"' -f4)"; \
    fi; \
    echo "${TSV}" > /out/tailscale-version \
 && curl -fsSL -o /tmp/ts.tgz "https://pkgs.tailscale.com/stable/tailscale_${TSV}_amd64.tgz" \
 && tar -C /tmp -xzf /tmp/ts.tgz \
 && cp "/tmp/tailscale_${TSV}_amd64/tailscale" "/tmp/tailscale_${TSV}_amd64/tailscaled" /out/ \
 && rm -rf /tmp/ts.tgz "/tmp/tailscale_${TSV}_amd64"

# -----------------------------------------------------------------------------
# Stage 3b: homepage-src —— HomePage 成品直取官方镜像（D5：v2 起无二进制资产，改镜像提取）
# -----------------------------------------------------------------------------
FROM ghcr.io/gethomepage/homepage:latest AS homepage-src

# -----------------------------------------------------------------------------
# Stage 4: final —— 合并成品，启动入口，清理
# -----------------------------------------------------------------------------
FROM base AS final

ARG DEFAULT_LANG=zh_CN.UTF-8
ENV LANG=${DEFAULT_LANG} \
    TZ=Asia/Shanghai \
    NVM_DIR=/opt/nvm \
    GOPATH=/home/dev/go

# 1) 语言工具链成品（Node/NVM 全局包随 NVM 目录进入；Go 工具链本体保留供日常开发）
COPY --from=toolchain-build /opt/nvm /opt/nvm
COPY --from=toolchain-build /usr/local/go /usr/local/go
COPY --from=toolchain-build /out/gobin/ /usr/local/bin/
COPY --from=toolchain-build /out/auth-gate /usr/local/bin/auth-gate
COPY --from=toolchain-build /usr/local/bin/bun /usr/local/bin/bun
COPY --from=toolchain-build /out/skel-dsh/ /etc/skel/.dsh/profiles/desktop/
COPY --from=toolchain-build /out/skel-magpie/ /etc/skel/.config/magpie/
COPY config/dsh/settings.yaml /etc/skel/.dsh/settings.yaml
RUN chmod +x /usr/local/bin/* 2>/dev/null || true \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

# 2) 交互环境成品
COPY --from=config /usr/share/oh-my-zsh /usr/share/oh-my-zsh
COPY --from=config /etc/skel/ /etc/skel/
COPY --from=config /usr/local/share/fonts/ /usr/local/share/fonts/
RUN fc-cache -f >/dev/null 2>&1 || true

# 3) 服务成品
COPY --from=services /out/ /usr/local/bin/
COPY --from=homepage-src /app/ /opt/homepage/

# 4) 配置与启动入口
COPY config/caddy/Caddyfile /etc/devbox/caddy/Caddyfile
COPY config/homepage/ /opt/homepage/config/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/decrypt.sh scripts/restore.sh /usr/local/bin/
COPY secrets/manifest.json /usr/local/share/devbox/manifest.json
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/decrypt.sh /usr/local/bin/restore.sh \
      /usr/local/bin/ttyd /usr/local/bin/filebrowser \
      /usr/local/bin/caddy /usr/local/bin/tailscale /usr/local/bin/tailscaled /usr/local/bin/auth-gate \
 && mkdir -p /home/dev/data /run/devbox \
 && chmod 755 /home/dev/data

# HomePage 端口与监听
ENV HOMEPAGE_PORT=3000

EXPOSE 22 8080
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
