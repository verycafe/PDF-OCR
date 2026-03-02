
## ☁️ 部署指南

### 推荐方案：Railway (最快/最简单)

由于本项目已经包含 `Dockerfile` 且依赖 Python/Node 环境，**Railway** 是最快部署的选择，因为它能自动识别 Dockerfile 并构建。

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
3. **构建并启动**：
   ```bash
   docker-compose up -d --build
   ```
4. 访问 `http://服务器IP:5001`。

### 注意事项
- **PaddleOCR 内存占用**：OCR 模型加载需要一定内存，建议服务器内存至少 **2GB** (推荐 4GB)。
- **构建时间**：由于需要安装 PyTorch 和 PaddlePaddle，首次构建可能需要 5-10 分钟。
