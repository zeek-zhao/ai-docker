# docker/block.Dockerfile — 参数化块镜像（FR-B2/B3，docs/01 §11、§12）
# 目标环境：Linux（仓库相对路径；仓库根 AGENT.md）。
#
# 继承链约束（FR-B2，ADR-004）：块镜像只继承 L0 工具链镜像；
# manifest 索引不进继承链——索引经运行时卷 / CI 制品注入，禁止
# FROM 任何 manifest-index 形态的基础镜像。
ARG TOOLCHAIN_IMAGE=repo-mirror-sync/toolchain:L0

FROM ${TOOLCHAIN_IMAGE}

# 块参数（SC-M2-02）：BUILD_BLOCK 取 config/policy.yaml blocks[].id；
# 块体积上限等策略一律出自 config/*.yaml，本文件不硬编码（AGENTS §3.3）。
ARG BUILD_BLOCK
ARG BLOCK_VERSION=0

LABEL org.opencontainers.image.title="repo-mirror-sync block ${BUILD_BLOCK}"
LABEL org.opencontainers.image.version="${BLOCK_VERSION}"

RUN mkdir -p /opt/block /workspace

# 块内容物：仓库清单 + 路径绑定表（FR-B3，docs/01 §11.2）。
# bindings.json 由构建流程生成后随上下文传入；缺失即构建失败（fail-fast）。
COPY blocks/${BUILD_BLOCK}/ /opt/block/
RUN test -f /opt/block/bindings.json \
    || (echo "bindings.json 缺失：块 ${BUILD_BLOCK} 未生成绑定表（FR-B3）" && exit 1)

# 交付约定（FR-B4）：本镜像产物由 CI 统一做全层加密与 sha256 tag
# （见 .github/workflows/build-block.yml），镜像本身保持明文层以支持分层拉取。
