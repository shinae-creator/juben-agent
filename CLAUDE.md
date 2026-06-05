# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

短剧 Agent 创作工作站 — 基于 Streamlit 的纯 Web 端短剧剧本 AI 生成工具。编剧无需接触终端，在网页上完成：输入题材 → AI 构思大纲 → 审核确认 → AI 拆分 N 集卡点 → 审核确认 → 流式生成剧本对白 → 一键下载。

## 当用户要求部署本项目时的自动化流程

如果用户说"帮我部署这个项目"或"帮我跑起来"，按以下步骤执行：

### 第一步：拉取代码

```powershell
git clone https://github.com/shinae-creator/juben-agent.git
cd juben-agent
```

如果用户电脑没有 git，引导用户安装 Git for Windows（https://git-scm.com/download/win）或直接下载 ZIP。

### 第二步：检查 Python 环境

```powershell
py --version
```

如果 `py` 命令不存在：
- **必须引导用户安装 Python 3.10+**：https://www.python.org/downloads/
- 安装时**务必勾选 "Add Python to PATH"**（底部复选框）
- 安装完成后让用户重新打开终端再试

### 第三步：配置 API Key

检查 `.env` 文件是否存在：
```powershell
Test-Path .env
```

如果不存在，引导用户创建：
1. 注册 DeepSeek 账号：https://platform.deepseek.com
2. 充值并创建 API Key
3. 在项目目录创建 `.env` 文件，内容：
```ini
LLM_MODEL=openai/deepseek-v4-pro
LLM_API_KEY=sk-你的密钥
LLM_API_BASE=https://api.deepseek.com
```

可直接复制 `.env.example` 后让用户替换密钥。**不要让用户手动输入密钥到聊天中**。

### 第四步：安装依赖

```powershell
py -m pip install -r requirements.txt
```

### 第五步：启动服务

```powershell
# 清理旧缓存（避免加载旧字节码）
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force agents\__pycache__ -ErrorAction SilentlyContinue

# 启动
py -m streamlit run app.py --server.headless true --server.port 8501
```

启动后浏览器打开 `http://localhost:8501`。

### 第六步：验证

```powershell
py -c "from agents.orchestrator import check_llm_connection; ok, msg = check_llm_connection(); print(msg)"
```

### 常见问题处理

| 症状 | 原因 | 处理 |
|------|------|------|
| `py` 命令找不到 | Python 未安装或没勾 Add to PATH | 重装 Python 并勾选 |
| `No module named 'streamlit'` | 依赖未安装 | 执行 `py -m pip install -r requirements.txt` |
| 端口 8501 被占用 | 已有 Streamlit 在跑 | 先 `taskkill /F /IM python.exe`，或换端口 `--server.port 8502` |
| LLM 连接失败 | API Key 错误或网络不通 | 检查 `.env` 密钥、检查能否访问 api.deepseek.com |
| 修改代码后不生效 | 字节码缓存 | 删除 `__pycache__` 再重启 |
| 想先测试不花钱 | 未开测试模式 | 侧边栏勾选 `🧪 测试模式`，零费用秒出结果 |

## 部署（给新电脑用）

## 部署（给新电脑用）

此项目面向非技术编剧用户，必须提供**零终端**的启动体验。

### 新电脑初始化（3 步）

```
1. 安装 Python 3.10+（必须勾选 "Add Python to PATH"）
2. 创建 .env 文件，填入 DeepSeek API Key（参照 .env.example）
3. 双击 启动.bat
```

### 交付文件清单

以下文件是他人部署所需（已在 git 中）：

| 文件 | 用途 |
|------|------|
| `启动.bat` | 双击自动装依赖 + 启动服务，零终端操作 |
| `requirements.txt` | pip 依赖清单（streamlit, litellm, pydantic, python-dotenv） |
| `.env.example` | API Key 配置模板，复制为 `.env` 后填入真实密钥 |
| `README.md` | 用户面向的完整部署指南 + FAQ |

### .env 配置

```ini
LLM_MODEL=openai/deepseek-v4-pro
LLM_API_KEY=sk-你的DeepSeek密钥
LLM_API_BASE=https://api.deepseek.com
```

`.env` 在 `.gitignore` 中，不会被提交。`.env.example` 是模板文件，会被提交。

### 启动.bat 行为

- 检测 Python 是否安装（`py --version`）
- 自动执行 `py -m pip install -r requirements.txt`
- 启动 Streamlit 于 8501 端口
- 浏览器打开 `http://localhost:8501`

### 依赖

```
streamlit>=1.58.0    # Web UI 框架
litellm>=1.87.0      # LLM 统一调用层（兼容 OpenAI/DeepSeek 等）
pydantic>=2.13.4     # 结构化数据校验
python-dotenv>=1.2.2 # .env 环境变量加载
```

## 常用命令

```powershell
# 启动（Windows，必须用 py -m，不能用 bash 的 streamlit 命令）
py -m streamlit run app.py --server.headless true --server.port 8501

# 或双击 启动.bat（自动安装依赖 + 启动）

# 重启前务必清除 Python 字节码缓存，否则修改不生效
taskkill /F /IM streamlit.exe 2>$null; taskkill /F /IM python.exe 2>$null
Remove-Item -Recurse -Force "L:\vscod\juben-agent\__pycache__" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "L:\vscod\juben-agent\agents\__pycache__" -ErrorAction SilentlyContinue

# 验证 prompt / LLM 连接
py -c "from agents.prompts import fmt_episode; s, u = fmt_episode(20, 'test'); print('20 instances:', s.count('20 集'))"
py -c "from agents.orchestrator import check_llm_connection; ok, msg = check_llm_connection(); print(msg)"
```

## 架构

```
app.py                     # Streamlit 前端（~1000行），UI + session_state + 流式渲染
├── config.py              # LLM 参数 + .env 加载（python-dotenv）
├── llm_config.py          # 多模型配置管理，JSON 持久化到 .claude/llm_configs.json
├── history.py             # 生成记录，保存到 generations/<剧名>_<时间戳>/
└── agents/
    ├── __init__.py         # 导出 Orchestrator
    ├── orchestrator.py     # Agent 矩阵编排器：三阶段流水线 + 流式/非流式 LLM 调用
    ├── prompts.py          # 三大 Agent 系统提示词（V2 JSON + LEGACY markdown）
    ├── schemas.py          # Pydantic v2 EpisodeCard 数据模型（4维评分）
    ├── episode_parser.py   # JSON/旧格式双向解析器 + 序列化
    └── mock.py             # 测试模式 Mock 数据（V2 结构化 + 评分曲线）
```

### 数据流

```
用户输入题材 → st.session_state.topic
  → Orchestrator.generate_outline_stream()  → outline → outline_editor_v{N}  widget
  → Orchestrator.generate_episodes_stream() → episode_list → episode_editor_v{N} widget
  → Orchestrator.generate_script_stream() → script_content → 下载 / 保存
```

### 状态机

`st.session_state.workflow_stage`: `input` → `planning` → `outline_review` → `episode_review` → `generating` → `done`

### 流式架构关键点

- 每个阶段有钩子（hook）设置标记位（如 `_outline_streaming`），不阻塞渲染
- 实际流式生成在右侧面板的 if-block 中执行，逐 token 更新 `st.empty()` placeholder
- `st.rerun()` 在流式完成后触发，将内容从右侧画布转移至左侧卡点卡片
- 每个阶段独立的 `gen_start_time` 计时

## 关键实现细节

### Widget 状态版本化（v5 修复的核心 bug）

Streamlit 的 `st.text_area(value=..., key=...)` 有一个陷阱：widget 一旦渲染，后续 rerun 中 `value=` 参数被忽略，以 key 对应的内部状态为准。如果流式生成前 text_area 先渲染了空内容，流式完成后 `value=` 传入新内容也会被旧空状态覆盖。

**解决方案**：用版本号生成新 key。每次 AI 生成/导入新内容时 `_bump_outline_version()` / `_bump_episode_version()` 递增版本号 → `key=f"outline_editor_v{version}"` 是全新 key → Streamlit 把 `value=` 当作初始值。

此模式也适用于 selectbox、number_input 等其他 widget。

### Streamlit 铁律

- 不能在 widget 渲染后手动写 `st.session_state[widget_key] = value`，会报 `cannot be modified after the widget is instantiated`
- `py -m streamlit` 启动（不是 `streamlit` 直接命令），因为 Windows 环境 PATH 不一致
- 修改 `.py` 文件后必须清理 `__pycache__` 再重启，否则 Python 加载旧字节码

### LLM 配置

- `.env` 文件持久化 API key，`config.py` 和 `llm_config.py` 启动时通过 `python-dotenv` 自动加载
- `.env` 已在 `.gitignore` 中，不会提交
- 前端 `🔌 LLM 模型配置` 面板可新增/切换/删除模型，保存到 `.claude/llm_configs.json`
- `Orchestrator.__init__` 接受 `model/api_key/api_base/total_episodes` 参数，覆盖 `config.py` 默认值
- `_llm_call()` 和 `_llm_stream()` 的签名是 `(system_prompt, user_prompt, temperature, max_tokens, model=None, api_key=None, api_base=None)` — 最后三个参数可选，传 None 时使用模块级默认值

### Prompt 动态集数

所有 prompt 均使用 `{total_episodes}` / `{groups}` 占位符，由 `fmt_planner(total_episodes, topic)` / `fmt_episode(total_episodes, outline)` 运行时填充。`groups = total_episodes // 10`。

### 测试模式

侧边栏 `🧪 测试模式` 复选框开启后，所有 LLM 调用替换为 `agents/mock.py` 的本地假数据，秒级完成，零 API 费用。Mock 函数签名与 Orchestrator 流式方法一致，接受 `total_episodes` 参数动态生成对应集数。

### .gitignore

排除 `__pycache__/`、`.claude/`、`*.pyc`、`test_*.py`、`.env`、`generations/`。

## V2 结构化分集系统（v8 新增）

### EpisodeCard 数据模型（`agents/schemas.py`）

Pydantic v2 模型，每集包含 4 维评分（0-10）：
- `conflict_intensity`（冲突烈度）、`pleasure_index`（爽感爆发度）、`hook_strength`（悬念钩子度）、`emotional_resonance`（情感共鸣度）
- `avg_score` 属性计算均分

### 数据流

```
LLM 输出 JSON 数组 → parse_episodes() → List[EpisodeCard]（可视化用）
                   → serialize_to_markdown() → episode_list 文本（对白引擎用）
```

### 解析器（`agents/episode_parser.py`）

- `parse_episodes(raw_text, total_episodes)` — JSON 优先 → 正则兜底 → 占位补齐
- `serialize_to_markdown(cards)` — 序列化为兼容旧格式
- `_parse_json_flexible()` — 处理围栏、尾逗号、截断
- `_parse_legacy_markdown()` — 旧格式正则提取，评分默认 5

### 前端双模式编辑

卡点二分集审定区支持切换：
- `📊 可视化大盘`：`st.dataframe` + `ProgressColumn` 进度条表格 + 单集 form 微调（slider 修改评分）
- `📝 原始文本`：保留旧 text_area 完全不变

### 新 session_state key

- `episode_cards: list[EpisodeCard]` — 结构化分集数据
- `episode_json_raw: str` — 原始 JSON 字符串
- `episode_editor_mode: str` — "visual" | "raw"

### Prompt 变更

- `EPISODE_SYSTEM_V2` / `EPISODE_USER_V2`：要求 LLM 输出纯 JSON 数组
- 旧 prompt 保留为 `EPISODE_SYSTEM_LEGACY` / `EPISODE_USER_LEGACY`
- `fmt_episode(total_episodes, outline, use_json=True)` 控制切换
