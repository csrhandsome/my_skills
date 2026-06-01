# Git 合并与推送操作指南

## 阶段一：SSH 密钥配置（只需做一次）

### 1. 生成密钥对

```bash
ssh-keygen -t ed25519 -C "murmur@mac"
# 一路回车即可（默认路径 + 空密码）
```

### 2. 查看公钥

```bash
cat ~/.ssh/id_ed25519.pub
```

复制输出的整行内容（以 `ssh-ed25519` 开头）。

### 3. 添加到 GitHub

1. 打开 GitHub → Settings → SSH and GPG keys
2. 点击 **New SSH key**
3. Title 填 `murmur@mac`，Key 粘贴公钥
4. 保存

### 4. 验证连接

```bash
ssh -T git@github.com
```

看到 `Hi xxx! You've been authenticated` 就成功了。

### 5. 把仓库远程地址改为 SSH

```bash
# 查看当前远程地址
git remote -v

# 改为 SSH 地址
git remote set-url origin git@github.com:用户名/仓库名.git
```

---

## 阶段二：--no-ff 合并分支

### 1. 拉取最新代码

```bash
git fetch origin
```

### 2. 切到目标分支

```bash
git checkout main
```

### 3. 拉取 main 最新内容

```bash
git pull origin main
```

### 4. 合并开发分支（--no-ff）

```bash
git merge --no-ff dev_murmur -m "Merge branch 'dev_murmur' into main"
```

### 5. 如果有冲突

```bash
# 查看冲突文件
git status

# 手动编辑冲突文件，解决后：
git add 冲突文件名
git commit -m "resolve merge conflicts"
```

---

## 阶段三：推送到远程

```bash
git push origin main
```

---

## 速查版（SSH 已配好的情况下）

```bash
git fetch origin
git checkout main
git pull origin main
git merge --no-ff dev_murmur -m "Merge branch 'dev_murmur' into main"
git push origin main
```

---

## --no-ff 是什么？

```
不用 --no-ff（fast-forward）：        用 --no-ff：

A---B---C---D  (main)                 A---B-------M  (main)
                                          \      /
                                           C---D  (dev_murmur)
```

`--no-ff` 强制创建一个合并提交（M），保留分支历史，能清楚看到哪些提交来自哪个分支。
