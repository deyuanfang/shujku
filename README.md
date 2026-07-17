# PersonalKB — 个人知识库管理系统

一个智能化的个人知识管理桌面应用，支持自动分析、分类、总结上传内容，
提供树状图和星空行星两种可视化模式。

## ✨ 核心功能

- **智能分析** — 自动分类、提取关键词、生成摘要
- **多种数据源** — 支持 文本/Markdown/PDF/图片(OCR)/网页链接/快速笔记
- **变更检测** — 重复上传时自动识别内容变化，重大变动主动提醒确认
- **知识图谱** — 树状图浏览分类层次，星空行星图探索知识关联
- **全文搜索** — SQLite FTS5 全文检索引擎，秒级响应
- **本地优先** — 所有数据存储在本地，无需网络

## 技术栈

| 层 | 技术 |
|------|------|
| 桌面壳 | Electron |
| 前端 | React 19 + TypeScript + TailwindCSS + D3.js |
| 后端 | Python FastAPI + SQLAlchemy + SQLite |
| NLP | jieba 分词 + TF-IDF 分类 |
| AI 增强 | Claude API (可选) |

## 快速开始

### 环境要求

- Node.js 18+
- Python 3.10+
- (可选) Claude API Key — 用于 AI 增强分析

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

### 3. 安装前端依赖 & 启动

```bash
cd frontend
npm install
npm run dev
```

### 4. 打开浏览器

访问 `http://localhost:5173`

### 5. 打包为桌面应用 (可选)

```bash
cd frontend
npm run electron:build
```

## 项目结构

```
knowledge-base/
├── backend/                # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py        # 应用入口
│   │   ├── config.py      # 配置管理
│   │   ├── database/      # 数据库模型
│   │   ├── api/           # REST API 路由
│   │   ├── services/      # 业务逻辑
│   │   │   ├── nlp_pipeline.py      # 中文NLP分类引擎
│   │   │   ├── content_extractor.py # 内容提取调度
│   │   │   └── parsers/            # 各类解析器
│   │   └── utils/         # 工具函数
│   └── data/              # 数据库和文件存储
├── frontend/              # React + Electron 前端
│   ├── electron/          # Electron 主进程
│   ├── src/
│   │   ├── pages/         # 页面组件
│   │   ├── components/    # UI 组件
│   │   ├── services/      # API 客户端
│   │   ├── store/         # Zustand 状态管理
│   │   └── types/         # TypeScript 类型
│   └── index.html
└── README.md
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/upload/file` | 上传文件 |
| POST | `/api/v1/upload/url` | 提交网页链接 |
| POST | `/api/v1/upload/note` | 快速笔记 |
| GET  | `/api/v1/documents` | 文档列表 |
| GET  | `/api/v1/documents/:id` | 文档详情 |
| GET  | `/api/v1/categories` | 分类树 |
| GET  | `/api/v1/search?q=` | 全文搜索 |
| GET  | `/api/v1/visualization/tree` | 树状图数据 |
| GET  | `/api/v1/visualization/galaxy` | 星系图数据 |
| GET  | `/api/v1/stats` | 统计概览 |
| GET  | `/api/v1/changes/alerts` | 变更提醒 |

## License

MIT
