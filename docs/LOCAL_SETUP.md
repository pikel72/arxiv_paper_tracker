# 本地环境配置指南

## 快速开始

### 1. 检查 Python 版本

确保已安装 Python 3.8 或更高版本：

```bash
python --version
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

**如果遇到网络问题，可使用国内镜像：**

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

复制示例配置文件：

```bash
cp .env.example .env
```

编辑 `.env` 文件，**最少需要配置**以下选项：

```bash
# 选择一个 AI 提供商（推荐使用通义千问，免费额度较大）
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo

# 配置对应的 API 密钥
QWEN_API_KEY=sk-your-qwen-api-key
```

### 4. 验证配置

运行缓存统计命令测试配置是否正确：

```bash
python src/main.py --cache-stats
```

如果能看到缓存统计信息，说明配置成功！

---

## 推荐的免费 AI 服务商

以下是**免费或有大额免费额度**的 AI 服务商，按推荐程度排序：

| 服务商 | 免费额度 | 获取方式 | 推荐指数 |
|--------|----------|----------|----------|
| **通义千问** | 大额免费 | [阿里云灵积平台](https://dashscope.aliyun.com/) | ⭐⭐⭐⭐⭐ |
| **智谱AI (GLM)** | 新用户免费 | [智谱AI开放平台](https://open.bigmodel.cn/) | ⭐⭐⭐⭐⭐ |
| **DeepSeek** | 非常便宜 | [DeepSeek开放平台](https://platform.deepseek.com/) | ⭐⭐⭐⭐ |
| **Kimi** | 有免费额度 | [Moonshot AI](https://platform.moonshot.cn/) | ⭐⭐⭐⭐ |

### 快速获取 API 密钥

#### 通义千问（推荐）

1. 访问 [阿里云灵积平台](https://dashscope.aliyun.com/)
2. 注册/登录
3. 进入控制台 → API-KEY管理
4. 创建新的 API-KEY

#### 智谱AI (GLM)

1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册/登录
3. 开通 API Key
4. 复制 API Key

#### DeepSeek

1. 访问 [DeepSeek开放平台](https://platform.deepseek.com/)
2. 注册/登录
3. 获取 API Key
4. 充值（按需计费，非常便宜）

---

## 完整配置示例

### 使用通义千问（推荐新手）

```bash
# .env 文件内容
AI_PROVIDER=qwen
AI_MODEL=qwen-turbo
QWEN_API_KEY=sk-your-qwen-api-key

# 邮件配置（可选）
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your_qq@qq.com
SMTP_PASSWORD=your_qq_authorization_code
EMAIL_FROM=your_qq@qq.com
EMAIL_TO=your@email.com

# ArXiv 配置
ARXIV_CATEGORIES=math.AP,cs.AI
MAX_PAPERS=20
SEARCH_DAYS=3

# 主题配置（可选，使用默认值）
PRIORITY_TOPICS=Navier-Stokes方程|湍流
SECONDARY_TOPICS=偏微分方程|机器学习

# 性能配置
MAX_THREADS=3
PRIORITY_ANALYSIS_DELAY=3
SECONDARY_ANALYSIS_DELAY=2
```

### 使用智谱AI (GLM)

```bash
AI_PROVIDER=glm
AI_MODEL=glm-4
GLM_API_KEY=your-glm-api-key
```

### 使用 DeepSeek

```bash
AI_PROVIDER=deepseek
AI_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

---

## 常见问题

### Q: 提示找不到模块错误

```bash
ModuleNotFoundError: No module named 'xxx'
```

**解决方法**：重新安装依赖

```bash
pip install -r requirements.txt --upgrade
```

### Q: API 调用失败

```bash
AI API调用失败: Invalid API Key
```

**解决方法**：
1. 检查 `.env` 文件中的 API Key 是否正确
2. 确认 API Key 是否有效且未过期
3. 确认选择了正确的 `AI_PROVIDER`

### Q: 邮件发送失败

**解决方法**：
1. QQ 邮箱必须使用授权码，不是登录密码
   - 登录 QQ 邮箱 → 设置 → 账户 → 开启 SMTP
   - 生成授权码
2. Gmail 需要开启两步验证并生成应用专用密码

### Q: PDF 下载失败

**解决方法**：
- 检查网络连接
- 某些 arXiv 论文可能没有 PDF 版本
- 查看 `papers/` 目录是否有权限

---

## 测试命令

### 测试单篇论文分析

```bash
python src/main.py --arxiv 2401.00001 -p 5
```

### 查看缓存统计

```bash
python src/main.py --cache-stats
```

### 清除所有缓存

```bash
python src/main.py --clear-cache all
```

### 测试本地 PDF 分析

```bash
# 先下载一个测试 PDF
wget https://arxiv.org/pdf/2301.00001.pdf -O test.pdf

# 分析本地 PDF
python src/main.py --pdf ./test.pdf -p 3
```

---

## Windows 快捷脚本

项目提供了 `run_tracker.bat` 脚本，双击运行即可进入交互式菜单：

1. 运行全流程分析
2. 单论文分析
3. 退出

**前提条件**：
- 已配置 `.env` 文件
- 已安装 Python 和依赖

---

## 环境变量速查表

| 配置项 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `AI_PROVIDER` | 是 | `qwen` | AI 提供商选择 |
| `AI_MODEL` | 是 | `qwen-turbo` | 模型名称 |
| `*_API_KEY` | 是* | - | 对应提供商的 API 密钥 |
| `ARXIV_CATEGORIES` | 否 | `math.AP` | 论文类别 |
| `MAX_PAPERS` | 否 | `50` | 最大论文数 |
| `SEARCH_DAYS` | 否 | `5` | 搜索天数 |
| `MAX_THREADS` | 否 | `5` | 最大线程数 |

*至少需要配置一个 AI 提供商的 API_KEY
