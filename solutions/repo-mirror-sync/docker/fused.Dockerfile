# docker/fused.Dockerfile — 融合视图定义（FR-B2，docs/01 §13，ADR-005）
# 目标环境：Linux（仓库相对路径；仓库根 AGENT.md）。
#
# 融合视图 = L0 工具链基座 + 运行时 OverlayFS lowerdir 叠加；
# 同名路径权威裁决规则唯一实现于 tools/overlay.py
# （config/policy.yaml overlay.*，AGENTS §3.6）——本文件只约定挂载形态，
# 不实现第二套裁决逻辑。
ARG TOOLCHAIN_IMAGE=repo-mirror-sync/toolchain:L0

FROM ${TOOLCHAIN_IMAGE}

LABEL org.opencontainers.image.title="repo-mirror-sync fused view"

# 运行时挂载点（SC-M2-03）：融合视图根与 manifest 索引挂载点。
RUN mkdir -p /workspace/merged /mnt/manifest /mnt/layers

# manifest 软链约定（FR-B2 / docs/01 §11）：视图内固定路径
# /workspace/manifest → 运行时卷挂载的索引，索引不进任何镜像继承链。
RUN ln -s /mnt/manifest /workspace/manifest

# 融合入口（docs/01 §13）：LOWERDIR 为冒号分隔的层目录序列
# （层序 = 选举规则裁决后的 stacking，由 verify-fuse 阶段生成）；
# max_lowerdir 上限校验唯一出处 config/policy.yaml（超出走两级融合）。
ENV LOWERDIR="/mnt/layers/toolchain:/mnt/layers/self-dev" \
    MOUNT_POINT="/workspace/merged"

# 实际挂载由消费侧运行时执行（ADR-011，docs/01 §13.1）；CI 验收=非特权
# 用户态等价校验 tools/fuse_verify.py（.github/workflows/verify-fuse.yml）。
CMD ["sh", "-c", "mount -t overlay overlay -o lowerdir=${LOWERDIR} ${MOUNT_POINT}"]
