
## ☁️ 部署指南

### 推荐方案：Railway (最快/最简单)

由于本项目已经包含 `Dockerfile` 且依赖 Python/Node 环境，**Railway** 是最快部署的选择，因为它能自动识别 Dockerfile 并构建。
当前镜像还会安装 LibreOffice Writer，用于将 `DOCX/DOC` 保真转换为 PDF 后再进入现有 OCR 流水线。

**优势**：
- **零配置**：自动检测 Dockerfile。
- **免费额度**：提供试用额度。
- **自动 HTTPS**：自动配置域名和 SSL。

**步骤**：
1. 注册/登录 [Railway](https://railway.app/)。
2. 点击 "New Project" -> "Deploy from GitHub repo"。
3. 选择 `PDF-OCR` 仓库。
4. Railway 会自动读取 Dockerfile 并开始构建。
5. 构建完成后，在 Settings -> Networking 中生成一个域名即可访问。

---

### 替代方案 2：Zeabur (国内访问较快)

**Zeabur** 对国内用户友好，且部署体验类似 Railway。

**步骤**：
1. 登录 [Zeabur](https://zeabur.com/)。
2. 创建新项目 -> 部署服务 -> Git。
3. 选择仓库，Zeabur 会自动识别并构建。

---

### 替代方案 3：自建 Docker (最可控)

如果你有自己的服务器（如阿里云、腾讯云、AWS），使用 Docker Compose 是最稳健的方式。

1. **确保服务器已安装 Docker 和 Docker Compose**。
2. **克隆代码**：
   ```bash
   git clone https://github.com/verycafe/PDF-OCR.git
   cd PDF-OCR
   ```
3. **可选：准备环境变量**：
   ```bash
   cp .env.example .env
   ```
4. **构建并启动**：
   ```bash
   bash scripts/docker-up.sh
   ```
   或者分两步执行：
   ```bash
   bash scripts/docker-build.sh
   docker compose up -d
   ```
5. 访问 `http://服务器IP:5001`。

补充说明：
- 当前 Dockerfile 会在镜像构建阶段自动执行前端 `npm ci` 和 `npm run build`
- Flask 会直接托管构建后的前端静态文件，所以服务器不需要额外安装 Node.js 或单独运行 Vite
- 镜像已经构建过时，可直接启动：
  ```bash
  bash scripts/docker-start.sh
  ```
- 停止服务可执行：
  ```bash
  bash scripts/docker-down.sh
  ```
- 查看最近日志可执行：
  ```bash
  bash scripts/docker-logs.sh
  ```
- 实时跟踪日志可执行：
  ```bash
  bash scripts/docker-logs.sh -f app
  ```
- 使用已构建镜像重启服务可执行：
  ```bash
  bash scripts/docker-restart.sh
  ```
- 查看容器状态和 HTTP 健康检查可执行：
  ```bash
  bash scripts/docker-status.sh
  ```
- 进入容器排障可执行：
  ```bash
  bash scripts/docker-shell.sh
  ```

### 注意事项
- **PaddleOCR 内存占用**：OCR 模型加载需要一定内存，建议服务器内存至少 **2GB** (推荐 4GB)。
- **构建时间**：由于需要安装 PyTorch、PaddlePaddle 和 LibreOffice，首次构建可能需要更久。

---

### GitHub Actions 自动发布镜像

仓库已添加工作流：
- [docker-publish.yml](/Users/tvwoo/Projects/PDF-OCR/.github/workflows/docker-publish.yml)

触发方式：
- push 到 `main`
- push `v*` 标签
- 手动 `workflow_dispatch`

发布目标：
```bash
ghcr.io/verycafe/pdf-ocr
```

常用标签：
```bash
ghcr.io/verycafe/pdf-ocr:latest
ghcr.io/verycafe/pdf-ocr:main
ghcr.io/verycafe/pdf-ocr:sha-<commit>
```

如果首次运行因为权限失败，请到 GitHub 仓库里确认：
- `Settings -> Actions -> General -> Workflow permissions`
- 允许 Actions 具备写入 packages 的权限
