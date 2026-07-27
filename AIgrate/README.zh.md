<p align="right">
  <strong>简体中文</strong> | <a href="README.md">English</a>
</p>

# AIgrate

基于 CLI 命令行的 AI 资源池管理系统。聚合多个 API 提供商，集中管理模型，智能路由请求。

## 功能

- **池模式 (Pool)** — 将多个 API Key 组织为一个池，自动故障转移、速率限制、并发控制、熔断重试
- **智能路由** — 请求自动分配到可用 Key，支持权重感知和速率感知路由
- **速率限制** — 滑动窗口限速器（次数/时间/Token）
- **多协议支持** — OpenAI、Azure、Anthropic、Hugging Face

## 快速开始

```bash
pip install -r requirements.txt
# 去配置 `data\pools.json`
python main.py
```

## 目录结构

```
AI池/
├── main.py            # 入口，启动 REPL
├── src/
│   ├── cli/           # CLI 交互层（REPL、编辑器、格式化输出）
│   └── core/          # 核心业务层（模型、路由、限速器、客户端）
├── test/              # 测试
├── docs/              # 设计文档
└── data/              # 配置
```

## 测试

```bash
pytest
```

## 许可证

MIT
