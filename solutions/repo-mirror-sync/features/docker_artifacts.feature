@M2
功能: 构建产物静态结构（docker/*.Dockerfile 与 .github/workflows/*）
  作为镜像同步的构建与融合入口
  三个 Dockerfile 与三个工作流满足 FR-B1~B4 的结构约束；
  本里程碑验收为静态结构校验，实际 Docker 构建 / CI 运行属
  Linux 服务器待执行项（诚实性，AGENTS §3.5；docs/06 §3 M2 行）

  @SC-M2-01
  场景: L0 工具链镜像固定 digest 且仅含工具链
    假如 Dockerfile 文件 "docker/toolchain.Dockerfile" 已存在
    那么 FROM 指令以 digest 固定基础镜像
    而且 安装层覆盖 git、age、overlayfs 三类工具
    而且 全文件不引用 latest 标签

  @SC-M2-02
  场景: 块镜像参数化且索引不进继承链
    假如 Dockerfile 文件 "docker/block.Dockerfile" 已存在
    那么 ARG 声明包含 BUILD_BLOCK
    而且 FROM 基于参数化工具链镜像
    而且 FROM 不引用索引镜像 manifest-index
    而且 全文件不引用 latest 标签

  @SC-M2-03
  场景: 融合视图定义含 OverlayFS 与 manifest 软链约定
    假如 Dockerfile 文件 "docker/fused.Dockerfile" 已存在
    那么 FROM 基于参数化工具链镜像
    而且 融合定义包含 lowerdir 挂载约定
    而且 融合定义包含 manifest 软链约定
    而且 全文件不引用 latest 标签

  @SC-M2-04
  场景: 三个工作流满足扫描周期与构建融合结构约束
    假如 工作流文件 "scan.yml" 已存在
    而且 工作流文件 "build-block.yml" 已存在
    而且 工作流文件 "verify-fuse.yml" 已存在
    那么 scan 工作流 cron 与 config 扫描周期一致
    而且 scan 工作流调用扫描器且凭据走环境变量
    而且 build-block 工作流按块参数化且产出绑定表
    而且 build-block 工作流含全层加密与 sha256 tag 规范
    而且 verify-fuse 工作流引用融合定义且解密凭据走环境变量
