# secrets/ —— 密钥与加解密流程说明（RK/PLAN §8）

> 文档编号：SK-001 · 版本：v1.0 · 2026-11-27 · 维护人：zeek.zhao

## ⚠️ 安全红线

- **`key.txt`（age 私钥）严禁提交仓库、严禁打入镜像**（AGENTS.md §4 / PLAN §8.6）。
- 本目录入库内容仅限：`manifest.json`、`*.age` 密文、`key.pub` 公钥、本 README。
- 本地执行前请确认 `.gitignore` 已排除 `secrets/key.txt`。

## 流程（PLAN §8.5）

```bash
# 0) 依赖（本地）：apt install age jq
# 1) 生成密钥对（一次性；已有私钥则校验并刷新公钥）
scripts/age-keygen.sh
# 2) 编辑 manifest.json 纳入要加密的目录/文件 → 本地存在对应源
# 3) 按清单加密（默认打包根 $HOME）
scripts/encrypt.sh
# 4) 打包发布（manifest + 密文 + 公钥 + 还原脚本 → 单一 tar.age）
scripts/pack.sh
# 5) 容器启动还原（自动）
#    compose 挂载: ./secrets:/secrets-pkg:ro 与 ./secrets/key.txt:/secrets/key.txt:ro
#    entrypoint → /usr/local/bin/restore.sh → decrypt.sh --owner dev:dev
```

## 手动 dry-run

```bash
docker exec zeek-devbox restore.sh --dry-run
```

## 密钥轮换

`age-keygen.sh` 换新钥后，需对全部条目重新 `encrypt.sh + pack.sh`（PLAN §8.5.4）。
