# docker/toolchain.Dockerfile — L0 工具链镜像（FR-B1，ADR-004，docs/01 §11）。
# 基础镜像经 Linux 服务器实测后填写（仓库根 AGENT.md）。
# 声明式策略不在镜像内散落硬编码：config/*.yaml 是唯一来源，镜像只承载工具。
#
# digest 固定策略（FR-B1）：维护期实测 digest 后填入，禁用 :latest。
# 构建期参数 UBUNTU_DIGEST 用于运维实测后显式注入替换占位：
#   （格式约束：sha256:<64位十六进制>；与静态校验一起防误用 digest 前缀）
#   （运维期外本地复验：AGENTS.md §3.5；已实测镜像可在数月内于 Linux 复验。）
ARG UBUNTU_DIGEST=sha256:REPLACE_AT_MAINTENANCE_TIME

FROM ubuntu:24.04@${UBUNTU_DIGEST}

LABEL org.opencontainers.image.title="repo-mirror-sync toolchain (L0)"
LABEL org.opencontainers.image.description="L0 工具链镜像：git + age（FR-B1）"
LABEL org.opencontainers.image.base.name="ubuntu:24.04"

# 工具链安装层（SC-M2-01）：git（版本审计）与 age（FR-B4 制品加密）。
# overlayfs-tools 移除（ADR-011，2026-11-28 实测 ubuntu:24.04 官方仓库无此包）：
# 融合验收由用户态等价校验 tools/fuse_verify.py 承担（docs/01 §13.1）；
# 内核 OverlayFS 挂载属消费侧运行时语义（Linux 服务器复验，阶段 4）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        age \
    && rm -rf /var/lib/apt/lists/*

# 烟囱探针（FR-B1）：安装层可用性即时断言，供 verify-fuse 复用。
RUN git --version && age --version && echo "toolchain-baseline" > /opt/.toolchain-baseline
