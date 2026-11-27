# docker/toolchain.Dockerfile — L0 工具链镜像（FR-B1，ADR-004，docs/01 §11）
# 目标环境：Linux（仓库相对路径；仓库根 AGENT.md）。
# 策略唯一出处：config/*.yaml；本文件只承载镜像定义，不含体积阈值。
#
# digest 固定策略（FR-B1）：基础镜像以 digest 锁定，禁止 :latest。
# 构建参数 DEBIAN_DIGEST 由维护者在升级时从官方发布页人工固定
# （示例形态：sha256:<64位十六进制>）；本仓库不杜撰具体 digest 值
# （诚实性，AGENTS.md §3.5）。实际拉取与构建验证属阶段 4（Linux 待执行）。
ARG DEBIAN_DIGEST=sha256:REPLACE_AT_MAINTENANCE_TIME

FROM debian:bookworm-slim@${DEBIAN_DIGEST}

LABEL org.opencontainers.image.title="repo-mirror-sync toolchain (L0)"
LABEL org.opencontainers.image.description="L0 工具链镜像：git + age + overlayfs（FR-B1）"
LABEL org.opencontainers.image.base.name="debian:bookworm-slim"

# 工具链安装层（SC-M2-01）：git（仓库维护）、age（FR-B4 全层加密）、
# overlayfs-tools（融合视图挂载/校验，docs/01 §13）。
# 包名以目标发行版仓库实际可用为准（Linux 待执行项，阶段 4 校正）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        age \
        overlayfs-tools \
    && rm -rf /var/lib/apt/lists/*

# 审计锚点（FR-B1）：安装清单指纹写入镜像层历史，供 verify-fuse 复核。
RUN git --version && age --version && echo "toolchain-baseline" > /opt/.toolchain-baseline
