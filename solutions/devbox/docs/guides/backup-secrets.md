# devbox-secrets —— DevBox 凭证备份（zeek-zhao/backup）

> 文档编号：BK-001 · 版本：v1.0 · 日期：2026-11-28 · 用途：DevBox 全套凭证密文异地备份（TD-009/T13.8，需求方确认直接推送）

## 1. 内容清单

| 文件 | 说明 |
|------|------|
| `devbox-secrets.tar.age` | 发布包（age 加密）：manifest.json + ssh.tar.age（三算法 SSH 密钥对：ed25519/rsa4096/ecdsa-p256）+ gitconfig.age + tokens.env.age（GH_TOKEN）+ key.pub + decrypt.sh/restore.sh |
| `key.pub` | age 公钥（可公开，仅用于加密） |

## 2. 解密使用（需 age 私钥）

```bash
# 私钥 key.txt 不在本仓（本地保管点：部署机 /home/jenkins/zeek_work/devbox-secrets/key.txt，0600）
tar xf devbox-secrets.tar.age          # 得到 manifest/密文/脚本
KEY=$(cat /path/to/key.txt)
age -d -i key.txt devbox-secrets.tar.age > devbox-secrets.tar   # 先解外层
tar xf devbox-secrets.tar && cat manifest.json          # 逐条目再解内层密文
# 或直接在 DevBox 容器内：挂载解包目录为 /secrets-pkg(ro) + 私钥挂 /run/devbox/key.txt，entrypoint 自动还原
```

## 3. 保管与轮换约定（D29 取舍）

1. age 私钥（key.txt）**只存本地部署机**，严禁入库/入镜像/入聊天记录；
2. 本仓只存密文+公钥——泄漏密文无 key 不可解（age X25519）；
3. 密钥轮换：`age-keygen` 生成新 key.txt → 重跑 `scripts/encrypt.sh` 全量重加密 → 覆盖本仓文件并更新 key.pub；
4. SSH 密钥/token 疑似泄漏：直接在对应平台吊销重签（本包重加密即可）。

## 4. 修订历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-11-28 | 首版（SSH 三算法+gitconfig+GH token 密文包） |
