# syntax=docker/dockerfile:1
# =============================================================================
# Dockerfile —— devbox 多阶段分层构建
# 文档编号：BD-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao
# 阶段：base → toolchain-build → config → services → final
# 构建：docker build --target final -t devbox:latest .
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
      silversearcher-ag fd-find bat ncdu btop httpie tldr git-delta \
      procps iproute2 \
 && ln -sf /usr/bin/fdfind /usr/local/bin/fd \
 && ln -sf /usr/bin/batcat /usr/local/bin/bat \
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
# M15/D38：auto = 构建时解析最新稳定 tag（git ls-remote，无 API 限流）；也可显式钉版本（如 v0.40.3）
ARG NVM_VERSION=auto
ARG NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG GO_VERSION=auto
ARG GO_PROXY=https://goproxy.cn,direct
# M12：DSH CLI 版本升级参数（升级方法见 docs/guides/upgrade.md；须在使用前声明）
# M15/D38：auto = 构建时装最新（dist-tags.latest；插件兼容由 tools/plugin-version-match.sh 机制兜底）
ARG DSH_NPM_SPEC="@deepseek-ai/dsh@latest"

ENV NVM_DIR=/opt/nvm \
    NVM_NODEJS_ORG_MIRROR=${NVM_NODEJS_ORG_MIRROR} \
    GOBIN=/out/gobin \
    GOPATH=/out/gopath

# 1) NVM + Node LTS + 前端全局工具（PLAN §4.2；M15/D38：NVM_VERSION=auto 时解析最新稳定 tag）
RUN mkdir -p "${NVM_DIR}" \
 && if [ "${NVM_VERSION}" = "auto" ]; then \
      NVMTAG="$(git ls-remote --tags --refs "${GH_PROXY}https://github.com/nvm-sh/nvm.git" | awk -F/ '{print $NF}' | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)"; \
    else NVMTAG="${NVM_VERSION}"; fi \
 && echo "[nvm] version=${NVMTAG}" \
 && git clone --depth 1 --branch "${NVMTAG}" "${GH_PROXY}${NVM_REPO}" "${NVM_DIR}" \
 && . "${NVM_DIR}/nvm.sh" \
 && nvm install --lts \
 && nvm alias default 'lts/*' \
 && npm config set registry "${NPM_REGISTRY}" \
 && npm install -g pnpm yarn typescript tsx eslint prettier vite \
 && npm install -g --allow-scripts=@deepseek-ai/dsh-subprocess-local,koffi,node-pty,protobufjs "${DSH_NPM_SPEC}" \
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
 && go install github.com/gokcehan/lf@latest \
 && rm -rf /out/gopath/pkg

# 4) auth-gate 会话鉴权微服务（R4 方案，源码在 config/caddy/authgate）
COPY config/caddy/authgate/ /src/authgate/
RUN cd /src/authgate \
 && CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/auth-gate . \
 && rm -rf /src/authgate

# 5) Bun（magpie 插件 workspace 依赖管理；restore-notes §0/§2.1；M15/D38：auto=release 最新）
ARG BUN_VERSION=auto
RUN --mount=type=secret,id=gh_token,target=/run/secrets/gh_token,required=false set -eux; \
    if [ "${BUN_VERSION}" = "auto" ]; then \
      if [ -r /run/secrets/gh_token ]; then \
        BUNV="$(curl -fsSL -H "Authorization: Bearer $(cat /run/secrets/gh_token)" https://api.github.com/repos/oven-sh/bun/releases/latest | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)"; \
      else \
        BUNV="$(curl -fsSL https://api.github.com/repos/oven-sh/bun/releases/latest | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4)"; \
      fi; \
    else BUNV="bun-${BUN_VERSION}"; fi \
 && echo "[bun] tag=${BUNV}" \
 && curl -fsSL -o /tmp/bun.zip \
      "${GH_PROXY}https://github.com/oven-sh/bun/releases/download/${BUNV}/bun-linux-x64.zip" \
 && cd /tmp && unzip -q bun.zip && mv bun-linux-x64/bun /usr/local/bin/bun \
 && chmod +x /usr/local/bin/bun && rm -rf /tmp/bun.zip /tmp/bun-linux-x64 \
 && bun --version

# 6) DSH 档案骨架（TD-003/D12 + M10/D26：快照结构 + 构建期 pnpm install；凭证零入库）
#    M10 排障：23 依赖中 dsh-at-file 的 peer（@deepseek-ai/dsh-client-runtime）会拉整条私有 rc 依赖树
#    （dsh-compact 等不在公共 registry）→ install 全断且被 `| tail` 管道吞错（exit=tail=0），镜像 node_modules 为空。
#    D26：构建期 jq 剔除 dsh-at-file（22 个可装插件保留）+ set -o pipefail 让安装失败即断。
#    产物 /out/skel-dsh/ → final 拷至 /etc/skel/.dsh/profiles/desktop/；web-profile 模板另出一份供 entrypoint 首启播种
#    （DSH_NPM_SPEC 已在阶段顶部 ARG 区声明，见 GO_PROXY 下方）
COPY config/dsh/profile-package.json /out/skel-dsh/package.json
COPY config/dsh/cordis.yml config/dsh/cordis.patch.yml /out/skel-dsh/
# M11/D27：pnpm store 固定到家目录（消除运行时「Switching to the store…requires purging」全量重装诱因——
# 构建期 store 路径与运行时不同会触发该提示；固定后插件更新走增量下载，无需 purge）
RUN printf 'store-dir=/home/dev/.pnpm-store\n' > /out/skel-dsh/.npmrc
RUN cd /out/skel-dsh \
 && jq 'del(.dependencies."dsh-at-file", .dependencies."dsh-better-sidebar") | .dsh.profile.bundles |= map(select(. != "dsh-at-file" and . != "dsh-better-sidebar"))' package.json > p.tmp && mv p.tmp package.json \
 && . "${NVM_DIR}/nvm.sh" && nvm use default >/dev/null \
 && pnpm install --frozen-lockfile=false --prefer-offline \
      --allow-build=koffi,node-pty,protobufjs,esbuild,@swc/core > /tmp/pi.log 2>&1 || { tail -20 /tmp/pi.log; exit 1; } \
 && tail -3 /tmp/pi.log \
 && [ -d node_modules/@deepseek-ai ] \
 && rm -rf node_modules/.cache /tmp/pi.log \
 && cp -a /out/skel-dsh /out/skel-dsh-web

# 7) Magpie 插件骨架（TD-003/Q3：page-free-tokens 本地 tgz 缺失已剔除，其余 bun install）
#    产物 /out/skel-magpie/ → final 拷至 /etc/skel/.config/magpie/
COPY config/magpie/plugins-package.json /out/skel-magpie/plugins/package.json
COPY config/magpie/plugins.json config/magpie/mcp-hub-servers.json /out/skel-magpie/
RUN cd /out/skel-magpie/plugins \
 && bun install 2>&1 | tail -3

# -----------------------------------------------------------------------------
# Stage 2: config —— 交互环境：Oh My Zsh(ys) / vim-fast / LazyVim / tmux / tmuxs
# -----------------------------------------------------------------------------
FROM base AS config

ARG GH_PROXY=""
ARG OMZ_REPO="https://github.com/ohmyzsh/ohmyzsh.git"
ARG ZSH_AUTOSUGGESTIONS_REPO="https://github.com/zsh-users/zsh-autosuggestions.git"
ARG ZSH_SYNTAX_HIGHLIGHTING_REPO="https://github.com/zsh-users/zsh-syntax-highlighting.git"
ARG OH_MY_TMUX_REPO="https://github.com/gpakosz/.tmux.git"
ARG LAZYVIM_STARTER_REPO="https://github.com/LazyVim/starter.git"
ARG LAZYVIM_STARTER_BRANCH=main

# 1) Oh My Zsh（系统级安装至 /usr/share/oh-my-zsh）+ 插件（PLAN §5.1；D19：主题改 ys，p10k 移除）
RUN git clone --depth 1 "${GH_PROXY}${OMZ_REPO}" /usr/share/oh-my-zsh \
 && git clone --depth 1 "${GH_PROXY}${ZSH_AUTOSUGGESTIONS_REPO}" /usr/share/oh-my-zsh/custom/plugins/zsh-autosuggestions \
 && git clone --depth 1 "${GH_PROXY}${ZSH_SYNTAX_HIGHLIGHTING_REPO}" /usr/share/oh-my-zsh/custom/plugins/zsh-syntax-highlighting \
 && rm -rf /usr/share/oh-my-zsh/.git /usr/share/oh-my-zsh/custom/plugins/*/.git

# 2) zsh/tmux 用户骨架（首次建用户即生效；tmuxs 工作台脚本见 config/tmux/tmuxs）
#    ubuntu 基础镜像 path-exclude 裁剪了 /usr/share/doc，omz fzf 插件 source 的示例脚本需从 fzf 源码补回（版本与 apt fzf 对齐）
COPY config/zsh/zshrc /etc/skel/.zshrc
RUN mkdir -p /usr/share/doc/fzf/examples \
 && curl -fsSL "https://raw.githubusercontent.com/junegunn/fzf/0.44.1/shell/key-bindings.zsh" -o /usr/share/doc/fzf/examples/key-bindings.zsh \
 && curl -fsSL "https://raw.githubusercontent.com/junegunn/fzf/0.44.1/shell/completion.zsh" -o /usr/share/doc/fzf/examples/completion.zsh
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
# Stage 2b: vim-fast —— vim 8/9 编译版 + websimple 配置 + 中文文档（M8/D20，风格参照 vim_compile.sh/self.sh/doc_zh.sh）
# -----------------------------------------------------------------------------
FROM base AS vim-fast

ARG GH_PROXY=""
ARG VIM_FAST_REPO="https://gitee.com/mirrorvim/vim-fast.git"
ARG VIM_MIRROR_REPO="https://gitee.com/mirrors/vim.git"
ARG VIM_DOC_URL="https://gitee.com/mirrorvim/vim-fast/releases/download/v1.0.2/doc.tar.gz"
ARG VIM_NAME=zeek.zhao
ARG VIM_EMAIL="zeek.zhao/zeek.zhao@devops.com"

# 1) 编译依赖（对照 vim-fast shell/vim_compile.sh：python3-dev + ncurses；gcc 在 base 已具备）
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-dev libncurses5-dev libncursesw5-dev wget ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# 2) 拉取 vim-fast 并按 websimple.sh 模式落配置（vimrc-no-plug → 身份化，sed 对照 shell/self.sh；CocInstall 段不启用）
RUN git clone --depth 1 "${VIM_FAST_REPO}" /tmp/vim-fast \
 && cp /tmp/vim-fast/vimrc-no-plug /root/.vimrc \
 && sed -i "s/chenxuan[^5]/${VIM_NAME}'/g" /root/.vimrc \
 && sed -i "s/ chenxuan/ ${VIM_NAME}/g" /root/.vimrc \
 && VIM_ADDR="$(echo "${VIM_EMAIL}" | awk -F/ '{print $NF}')" \
 && sed -i "s|^iab ;e .*|iab ;e ${VIM_ADDR}|" /root/.vimrc \
 && rm -rf /tmp/vim-fast

# 3) 编译安装 vim（对照 vim_compile.sh：huge + multibyte + python3 dynamic；顶替系统 vim）
#    注：上游 --enable-pythoninterp 为 python2 interp（需 python-dev），ubuntu 24.04 无 python2，故仅保留 python3
RUN git clone --depth 1 "${VIM_MIRROR_REPO}" /tmp/vim-src \
 && cd /tmp/vim-src \
 && ./configure --with-features=huge --enable-multibyte \
      --enable-python3interp=dynamic \
      --enable-gui=auto --enable-cscope --enable-largefile --enable-fail-if-missing \
      --prefix=/usr \
 && make -j"$(nproc)" \
 && make install \
 && rm -rf /tmp/vim-src \
 && vim --version | head -2

# 4) 中文帮助文档（doc_zh.sh v1.0.2；tar 内为 vimcdoc/doc 结构）
RUN curl -fsSL -o /tmp/vim-doc.tar.gz "${VIM_DOC_URL}" \
 && tar -C /tmp -xzf /tmp/vim-doc.tar.gz \
 && mkdir -p /root/.vim \
 && mv /tmp/vimcdoc/doc /root/.vim/doc \
 && rm -rf /tmp/vim-doc.tar.gz /tmp/vimcdoc

# -----------------------------------------------------------------------------
# Stage 3: services —— 服务二进制：ttyd / filebrowser / Caddy / HomePage / Tailscale
# -----------------------------------------------------------------------------
FROM base AS services

ARG GH_PROXY=""
# M15/D38：auto = 构建时解析最新 release（GHA runner 匿名 API 限流经 secret gh_token 解；本地构建匿名即可）
ARG TTYD_VERSION=auto
ARG LAZYGIT_VERSION=auto
ARG DUST_VERSION=auto
ARG FILEBROWSER_VERSION=auto
ARG TAILSCALE_VERSION=auto
ARG MAGPIE_VERSION=auto
ARG CADDY_DOWNLOAD_URL="https://caddyserver.com/api/download?os=linux&arch=amd64"
# 注：鉴权由独立 auth-gate + Caddy forward_auth 完成，无需额外 Caddy 模块

RUN set -eux; mkdir -p /out /opt

# 0) 版本探测（M15/D38：全部 auto 汇总到 /out/versions.env；探测失败回退已知稳定版）
RUN --mount=type=secret,id=gh_token,target=/run/secrets/gh_token,required=false set -eux; \
    if [ -r /run/secrets/gh_token ]; then \
      gh_latest() { curl -fsSL -H "Authorization: Bearer $(cat /run/secrets/gh_token)" "https://api.github.com/repos/$1/releases/latest" | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4; }; \
    else \
      gh_latest() { curl -fsSL "https://api.github.com/repos/$1/releases/latest" | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4; }; \
    fi; \
    TTYD_V="${TTYD_VERSION}";  [ "${TTYD_V}" = "auto" ]  && { TTYD_V="$(gh_latest tsl0922/ttyd)" || TTYD_V=""; }; [ -z "${TTYD_V}" ] && TTYD_V="1.7.7"; \
    LG_V="${LAZYGIT_VERSION}"; [ "${LG_V}" = "auto" ]   && { LG_V="$(gh_latest jesseduffield/lazygit)" || LG_V=""; }; [ -z "${LG_V}" ] && LG_V="v0.66.3"; \
    DUST_V="${DUST_VERSION}";  [ "${DUST_V}" = "auto" ] && { DUST_V="$(gh_latest bootandy/dust)" || DUST_V=""; }; [ -z "${DUST_V}" ] && DUST_V="v1.2.8"; \
    FB_V="${FILEBROWSER_VERSION}"; [ "${FB_V}" = "auto" ] && { FB_V="$(gh_latest filebrowser/filebrowser)" || FB_V=""; }; [ -z "${FB_V}" ] && { echo "[filebrowser] 探测失败，回退 v2.63.23"; FB_V="v2.63.23"; }; \
    MP_V="${MAGPIE_VERSION}";  [ "${MP_V}" = "auto" ]   && { MP_V="$(gh_latest yetone/magpie)" || MP_V=""; }; [ -z "${MP_V}" ] && MP_V="v0.1.4984"; \
    printf 'TTYD_V=%s\nLG_V=%s\nDUST_V=%s\nFB_V=%s\nMP_V=%s\n' "${TTYD_V}" "${LG_V}" "${DUST_V}" "${FB_V}" "${MP_V}" > /out/versions.env; \
    cat /out/versions.env

# 1.5) 增强工具（TD-009/T13.5/D32）：lazygit + dust（版本见 /out/versions.env）
RUN . /out/versions.env \
 && curl -fsSL "${GH_PROXY}https://github.com/jesseduffield/lazygit/releases/download/${LG_V}/lazygit_${LG_V#v}_Linux_x86_64.tar.gz" \
      | tar -xz -C /out lazygit \
 && curl -fsSL "${GH_PROXY}https://github.com/bootandy/dust/releases/download/${DUST_V}/dust-${DUST_V}-x86_64-unknown-linux-gnu.tar.gz" \
      | tar -xz -C /out --strip-components=1 dust-${DUST_V}-x86_64-unknown-linux-gnu/dust \
 && chmod +x /out/lazygit /out/dust

# 1) ttyd Web 终端（静态二进制）
RUN . /out/versions.env \
 && curl -fsSL -o /out/ttyd \
      "${GH_PROXY}https://github.com/tsl0922/ttyd/releases/download/${TTYD_V}/ttyd.x86_64" \
 && chmod +x /out/ttyd

# 2) filebrowser 文件共享（版本见 /out/versions.env）
RUN . /out/versions.env \
 && curl -fsSL -o /tmp/fb.tar.gz \
      "${GH_PROXY}https://github.com/filebrowser/filebrowser/releases/download/${FB_V}/linux-amd64-filebrowser.tar.gz" \
 && tar -C /out -xzf /tmp/fb.tar.gz filebrowser && rm -f /tmp/fb.tar.gz

# 3) Caddy（caddyserver.com 官方在线构建，标准模块）
RUN curl -fsSL -o /out/caddy "${CADDY_DOWNLOAD_URL}" && chmod +x /out/caddy

# 3b) Magpie CLI（订阅池化网关，TD-003/D11：yetone/magpie release 单二进制；版本见 /out/versions.env。
#     M15：官方无 Docker 镜像（ghcr.io/yetone/magpie 404 实测），维持 release 下载+auto 最新）
RUN . /out/versions.env \
 && curl -fsSL -o /out/magpie \
      "${GH_PROXY}https://github.com/yetone/magpie/releases/download/${MP_V}/magpie-cli-linux-amd64" \
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

# 6) 开发辅助工具（M8/D22：yq / hadolint / repo launcher 清华镜像）
RUN curl -fsSL -o /out/yq \
      "${GH_PROXY}https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64" \
 && curl -fsSL -o /out/hadolint \
      "${GH_PROXY}https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64" \
 && curl -fsSL -o /out/repo \
      "https://storage.googleapis.com/git-repo-downloads/repo" \
 && chmod +x /out/yq /out/hadolint /out/repo \
 && /out/yq --version \
 && /out/hadolint --version \
 && head -1 /out/repo | grep -q python

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
    GOPATH=/home/dev/go \
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt

# 1) 语言工具链成品（Node/NVM 全局包随 NVM 目录进入；Go 工具链本体保留供日常开发）
COPY --from=toolchain-build /opt/nvm /opt/nvm
COPY --from=toolchain-build /usr/local/go /usr/local/go
COPY --from=toolchain-build /out/gobin/ /usr/local/bin/
COPY --from=toolchain-build /out/auth-gate /usr/local/bin/auth-gate
COPY --from=toolchain-build /usr/local/bin/bun /usr/local/bin/bun
COPY --from=toolchain-build /out/skel-dsh/ /etc/skel/.dsh/profiles/desktop/
# web-profile 插件模板（M10/D26）：dsh web 运行时用 web 档案（desktop 是 Electron 专属，web 版不读取），
# 首启由 entrypoint 播种到 ~/.dsh/profiles/web，插件面板即出现完整插件列表
COPY --from=toolchain-build /out/skel-dsh-web/ /opt/devbox-skel/web-profile/
COPY --from=toolchain-build /out/skel-magpie/ /etc/skel/.config/magpie/
COPY config/dsh/settings.yaml /etc/skel/.dsh/settings.yaml
RUN chmod +x /usr/local/bin/* 2>/dev/null || true \
 && ln -sf /usr/local/go/bin/go /usr/local/bin/go \
 && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt

# 2) 交互环境成品（M8/D19：Meslo 字体段已随 p10k 移除）
COPY --from=config /usr/share/oh-my-zsh /usr/share/oh-my-zsh
COPY --from=config /etc/skel/ /etc/skel/
COPY --from=config /usr/share/doc/fzf/examples/ /usr/share/doc/fzf/examples/
COPY --from=vim-fast /root/.vimrc /etc/skel/.vimrc
COPY --from=vim-fast /root/.vim/ /etc/skel/.vim/
COPY config/tmux/tmuxs /usr/local/bin/tmuxs
# TD-009/T13.5：鼠标默认开启（oh-my-tmux 用户覆写层；useradd cp -a skel 落家目录）
COPY config/tmux/tmux.conf.local /etc/skel/.tmux.conf.local
RUN fc-cache -f >/dev/null 2>&1 || true \
 && chmod +x /usr/local/bin/tmuxs

# 3) 服务成品
COPY --from=services /out/ /usr/local/bin/
COPY --from=homepage-src /app/ /opt/homepage/

# 4) 配置与启动入口
COPY config/caddy/Caddyfile /etc/devbox/caddy/Caddyfile
COPY config/homepage/ /opt/homepage/config/
# M11/D28：版本匹配工具入镜像（dev 用户可直接使用）
COPY tools/ /usr/local/share/devbox/tools/
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/decrypt.sh scripts/restore.sh /usr/local/bin/
COPY secrets/manifest.json /usr/local/share/devbox/manifest.json
# M12/D29：Tailscale 等运行凭证的 age 密文随镜像分发（公开镜像仅含密文；解密私钥 key.txt 须 compose 挂载，严禁入库）
COPY secrets/*.age /usr/local/share/devbox/secrets/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/decrypt.sh /usr/local/bin/restore.sh \
      /usr/local/bin/ttyd /usr/local/bin/filebrowser \
      /usr/local/bin/caddy /usr/local/bin/tailscale /usr/local/bin/tailscaled /usr/local/bin/auth-gate \
 && mkdir -p /home/dev/data /run/devbox \
 && chmod 755 /home/dev/data

# HomePage 端口与监听
ENV HOMEPAGE_PORT=3000

EXPOSE 22 8080
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
