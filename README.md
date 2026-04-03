# URL Markdown Workbench

一个本地 Web 工作台，用来把网页链接转换成适合放进 Obsidian Vault 的 Markdown 文档。

你输入一条或多条 URL，系统会为每条链接生成一组本地文件：

- `raw.md`：抓取后的原始 Markdown
- `polished.md`：OpenAI 整理后的成稿
- `assets/`：下载到本地的图片附件

这些文件会直接写进你的 Obsidian Vault，所以 Obsidian 在这个项目里的角色主要是“本地输出目录”。

## 它能做什么

- 接收一条或多条网页 URL，并为每条 URL 创建独立任务
- 抓取网页正文，生成 `raw.md`
- 下载正文图片到本地 `assets/`
- 把图片引用统一改写成 Obsidian embed，例如 `![[assets/hero.png]]`
- 调用 OpenAI 将原始内容整理成更易读的 `polished.md`
- 在网页界面查看任务状态、原始稿、整理稿和附件列表
- 对失败任务发起重试

## 它不做什么

- 不生成 HTML 成稿
- 不提供云端托管、多用户协作或远程队列

## 工作方式

完整链路如下：

1. 你在首页输入一条或多条 URL
2. 后端为每条 URL 创建一个 `Document` 和一个异步 `process_url` 任务
3. Worker 抓取网页内容，生成 `raw.md`
4. 系统把远程图片下载到本地 `assets/`
5. OpenAI 基于 `raw.md` 输出排版更好的 `polished.md`
6. 前端展示状态、文件内容和失败信息

每条 URL 最终会写入这样的目录：

```text
<OBSIDIAN_VAULT_PATH>/<OBSIDIAN_OUTPUT_SUBDIR>/<YYYY-MM-DD>/<slug>-<hash8>/
├── raw.md
├── polished.md
└── assets/
```

示例：

```text
/Users/yourname/Documents/Obsidian Vault/url-markdown-workbench/2026-04-17/example-1a2b3c4d/
├── raw.md
├── polished.md
└── assets/
```

## 仓库结构

- `backend/`：FastAPI API、SQLite、任务编排、Worker
- `web/`：Next.js 前端工作台

## 运行要求

- Python 3.11+
- Node.js 20+
- `pnpm`
- 一个可写的 Obsidian Vault 本地目录
- 一个可用的 `OPENAI_API_KEY`

推荐但非必需：

- `defuddle`

如果安装了 `defuddle`，抓取质量通常会更好；如果没安装，系统会自动回退到内置抓取器。

## 5 分钟跑起来

### 1. 配置后端环境变量

进入后端目录并创建 `.env`：

```bash
cd backend
cp .env.example .env
```

至少需要填写这两个变量：

```env
OPENAI_API_KEY=sk-...
OBSIDIAN_VAULT_PATH=/Users/yourname/Documents/Obsidian Vault
```

可选变量：

- `OBSIDIAN_OUTPUT_SUBDIR`
  默认是 `url-markdown-workbench`
- `OPENAI_POLISH_MODEL`
  默认是 `gpt-5`
- `WORKER_POLL_INTERVAL_SECONDS`
  默认是 `1.0`

说明：

- `OBSIDIAN_VAULT_PATH` 是你本机上的 Obsidian Vault 根目录
- 当前配置只需要指定 Vault 路径

### 2. 启动后端 API

```bash
cd backend
python3 -m venv .venv-local
source .venv-local/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

默认监听：

```text
http://127.0.0.1:8000
```

### 3. 启动 Worker

另开一个终端：

```bash
cd backend
source .venv-local/bin/activate
python -m app.worker
```

Worker 会持续轮询数据库中的 `process_url` 任务。

### 4. 启动前端

再开一个终端：

```bash
cd web
cp .env.local.example .env.local
pnpm install
pnpm dev
```

默认地址：

```text
http://127.0.0.1:3000
```

### 5. 打开页面并开始使用

1. 访问 `http://127.0.0.1:3000`
2. 先测试 `Obsidian` 和 `OpenAI` 两个集成状态
3. 在输入框中一行填一条 URL
4. 提交后等待任务从 `queued` 进入 `capturing`、`polishing`、`completed`
5. 在右侧查看 `raw`、`polished` 和附件列表
6. 在 Obsidian 中打开同一个 Vault，就能看到生成的文件

## 环境变量

后端环境变量见 [backend/.env.example](backend/.env.example)。

常用变量：

- `DATABASE_URL`
  默认 `sqlite:///./document_workbench.db`
- `API_HOST`
  默认 `127.0.0.1`
- `API_PORT`
  默认 `8000`
- `FRONTEND_ORIGIN`
  默认 `http://127.0.0.1:3000`
- `WORKER_POLL_INTERVAL_SECONDS`
  Worker 轮询间隔
- `OPENAI_API_KEY`
  必填
- `OPENAI_BASE_URL`
  默认 `https://api.openai.com/v1`
- `OPENAI_POLISH_MODEL`
  用于生成 `polished.md`
- `OBSIDIAN_VAULT_PATH`
  必填
- `OBSIDIAN_OUTPUT_SUBDIR`
  输出子目录名

前端环境变量见 [web/.env.local.example](web/.env.local.example)。

- `NEXT_PUBLIC_API_BASE_URL`
  默认 `http://127.0.0.1:8000`

## 抓取方式

抓取服务会自动选择后端：

- 如果本机安装了 `defuddle`，优先执行：

```bash
defuddle parse <url> --md -o raw.md
```

- 如果未安装 `defuddle`，自动回退到内置的 `requests + HTMLParser` 抓取器

安装 `defuddle`：

```bash
npm install -g defuddle
```

说明：

- `defuddle` 是一个可选的网页转 Markdown CLI
- 如果你在 Worker 已运行之后才安装 `defuddle`，请重启 Worker

## 使用结果长什么样

对于每条 URL，你会得到：

- `raw.md`
  抓取后的原始内容，适合排错和比对
- `polished.md`
  LLM 整理后的版本，适合直接在 Obsidian 中阅读和继续编辑
- `assets/`
  图片附件目录

前端会展示：

- 最近文档列表
- 最近任务列表
- 当前文档的 `raw` / `polished` 两个视图
- 当前文档的本地图片附件

## 常见问题

### 1. 前端能打开，但任务一直不动

通常是 Worker 没启动。

检查是否有这个进程在运行：

```bash
cd backend
source .venv-local/bin/activate
python -m app.worker
```

### 2. Obsidian 集成测试失败

通常是 `OBSIDIAN_VAULT_PATH` 配错了，或者该目录不可写。

你填的应该是 Vault 的本地文件夹路径，例如：

```env
OBSIDIAN_VAULT_PATH=/Users/yourname/Documents/Obsidian Vault
```

### 3. OpenAI 测试失败

检查：

- `OPENAI_API_KEY` 是否正确
- `OPENAI_BASE_URL` 是否正确
- 当前 key 是否有对应模型访问权限

### 4. 生成了 `raw.md`，但没有 `polished.md`

通常表示抓取成功了，但 OpenAI 整理失败了。去前端的任务详情里看错误信息，或查看 Worker 终端输出。

### 5. 为什么没有使用 `defuddle`

检查命令是否存在：

```bash
which defuddle
```

如果命令存在但仍未生效，重启 Worker，因为抓取后端是在 Worker 进程内决定的。

### 6. 需要打开 Obsidian 桌面 App 吗

不是必须。

只要 `OBSIDIAN_VAULT_PATH` 指向一个本地目录，项目就能写文件。打开 Obsidian 桌面 App 只是为了更方便地查看和编辑生成结果。

## API 概览

- `GET /health`
- `GET /integrations/status`
- `POST /integrations/obsidian/test`
- `POST /integrations/openai/test`
- `POST /documents/process`
- `GET /documents`
- `GET /documents/{id}`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/retry`

## 开发验证

后端测试：

```bash
cd backend
source .venv-local/bin/activate
python -m pytest
```

前端构建：

```bash
cd web
pnpm build
```
