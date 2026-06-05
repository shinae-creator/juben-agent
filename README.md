# 🎬 短剧 Agent 创作工作站

基于 Streamlit 的纯 Web 端短剧剧本 AI 生成工具。编剧无需接触终端，在网页上完成：输入题材 → AI 构思大纲 → 审核确认 → AI 拆分 N 集卡点 → 审核确认 → 流式生成剧本对白 → 一键下载。

## 整体运行流程

```
编剧输入题材 → [卡点1] AI生成大纲 → 编剧审核确认
→ [卡点2] AI拆分N集卡点 → 编剧审核确认
→ [卡点3] AI逐字流式生成剧本对白 → 完成下载
```

6 阶段状态机控制全程：`input → planning → outline_review → episode_review → generating → done`

## 项目结构

```
app.py                     # Streamlit 前端（~750行），UI + session_state + 流式渲染
├── config.py              # LLM 参数 + .env 加载（python-dotenv）
├── llm_config.py          # 多模型配置管理，JSON 持久化到 .claude/llm_configs.json
├── history.py             # 生成记录，保存到 generations/<剧名>_<时间戳>/
└── agents/
    ├── __init__.py         # 导出 Orchestrator
    ├── orchestrator.py     # Agent 矩阵编排器：三阶段流水线 + 流式/非流式 LLM 调用
    ├── prompts.py          # 三大 Agent 系统提示词 + fmt_planner()/fmt_episode() 动态格式化
    └── mock.py             # 测试模式 Mock 数据，不烧 Token
```

## 启动方式

```powershell
# Windows（必须用 py -m，不能用 bash 的 streamlit 命令）
py -m streamlit run app.py --server.headless true --server.port 8501

# 重启前务必清除 Python 字节码缓存
taskkill /F /IM streamlit.exe 2>$null; taskkill /F /IM python.exe 2>$null
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force agents\__pycache__ -ErrorAction SilentlyContinue
```

---

## 后台模型运作模式

### 配置链路（从用户配置到 LLM 请求）

```
.env 文件                      llm_configs.json（用户自定义）
    ↓                                  ↓
config.py (默认值)              llm_config.py (合并 + 去重)
    ↓                                  ↓
    └───────────────┬──────────────────┘
                    ↓
    get_active_config(active_model) → {model, api_key, api_base}
                    ↓
    Orchestrator.__init__(model=, api_key=, api_base=, total_episodes=)
                    ↓
    _llm_call() / _llm_stream() → litellm.completion()
                    ↓
    POST https://api.deepseek.com/v1/chat/completions
```

- `.env`：持久化 API Key（gitignore），`python-dotenv` 在 `config.py` 和 `llm_config.py` 导入时自动加载
- `.claude/llm_configs.json`：用户在侧边栏「🔌 LLM 模型配置」面板新增/删除的模型，与默认配置合并，按 `model` 字段去重
- 默认配置不可删除，用户配置覆盖在默认之上

### 三阶段 Agent 矩阵

| 阶段 | Agent 角色 | 调用方式 | Prompt | temperature | max_tokens |
|------|-----------|---------|--------|-------------|------------|
| 大纲 | 爆款策划师 | `generate_outline_stream(topic)` | `fmt_planner(total_episodes, topic)` → `PLANNER_SYSTEM + PLANNER_USER` | 0.85 | 8,192 |
| 分集 | 分集架构师 | `generate_episodes_stream(outline)` | `fmt_episode(total_episodes, outline)` → `EPISODE_SYSTEM + EPISODE_USER` | 0.7 | 16,384 |
| 对白 | 对白引擎 | `generate_script_stream(topic, episode_list)` | `DIALOGUE_SYSTEM + DIALOGUE_USER`（无需集数占位） | 0.9 | 8,192 |

- 大纲和分集的 Prompt 使用 `{total_episodes}` / `{groups}` 占位符，由 `fmt_planner()` / `fmt_episode()` 运行时填充，`groups = total_episodes // 10`
- 分集生成有兜底机制：一次性生成全部 N 集失败时，自动降级为分批生成（每批 `EPISODES_PER_BATCH=10` 集）

### LLM 调用方式（流式 vs 非流式）

两种调用封装在 `agents/orchestrator.py` 中：

```python
# 非流式 — 一次性返回完整内容
_llm_call(system_prompt, user_prompt, temperature, max_tokens,
          model=None, api_key=None, api_base=None) → (content, TokenUsage)

# 流式 — 逐 token yield（打字机效果）
_llm_stream(system_prompt, user_prompt, temperature, max_tokens,
            model=None, api_key=None, api_base=None) → Generator[(token_text, usage_or_None)]
```

流式 yield 协议：

```python
yield "她缓缓推开门", None                         # 中间 chunk：token 文本 + usage=None
yield "", TokenUsage(input=500, output=2000)        # 最后一个：空文本 + TokenUsage 对象
```

前端消费循环（在 `app.py` 右侧画布区域）：

```python
for chunk, batch_usage in stream_gen:
    accumulated += chunk                        # 拼接到累积文本
    update_placeholder(accumulated)             # 打字机效果：更新 st.empty()
    if batch_usage:
        accumulate_token_counters(batch_usage)  # 累加 Token 用量到 st.session_state
```

### 底层 LLM 路由

`litellm` 作为统一抽象层，兼容所有 OpenAI 兼容 API。当前默认配置使用 DeepSeek：

```
model:    openai/deepseek-v4-pro
api_base: https://api.deepseek.com
```

实际请求等价于 `POST https://api.deepseek.com/v1/chat/completions`，携带 `Authorization: Bearer sk-xxx`。`model` 字段中的 `openai/` 前缀指示 litellm 使用 OpenAI 兼容协议发送请求。

### 前端无阻塞流式架构

用户提交题材后不直接调用 LLM，而是设置标记位 + `st.rerun()`：

```
用户点击提交 → workflow_stage = "planning" → st.rerun()
    ↓
下次渲染时检测到 planning + _outline_streaming 钩子
    ↓
在右侧面板 if-block 中执行流式生成
    ↓
每收到 token → 更新 st.empty() placeholder（打字机效果）
    ↓
流式结束 → 内容写入 session_state → stage 前移 → st.rerun()
    ↓
内容从右侧画布"落位"到左侧卡点卡片
```

每个阶段有独立的 `gen_start_time` 计时，互不干扰。

### 测试模式（零 API 费用）

侧边栏 `🧪 测试模式` 开启时，**完全不调用 LLM**。`agents/mock.py` 提供与 Orchestrator 签名一致的 Mock 生成器：

```python
if test_mode:
    stream_gen = generate_mock_outline_stream(topic, total_episodes=100)
else:
    orch = Orchestrator(...)
    stream_gen = orch.generate_outline_stream(topic)
```

Mock 函数根据 `total_episodes` 动态生成对应集数的假数据（大纲、分集、剧本），秒级完成，用于快速调试验证 UI 流程。

### 数据持久化

```
generations/
  <剧名>_<时间戳>/
    outline.txt       ← 卡点一确认时保存
    episodes.txt      ← 卡点二确认时保存
    script.txt        ← 剧本生成完成时保存
    metadata.json     ← Token 用量、耗时、模型名等元数据
```

剧名通过 `history.py` 的 `extract_title()` 从大纲中用正则提取，fallback 到题材文本。每个卡点确认时立即保存，不等到全部完成。

---

## 关键设计决策速查

| 问题 | 方案 |
|------|------|
| Widget 状态丢失 | 版本化 key，每次内容变化 `_bump_*_version()` 生成新 widget |
| 字节码缓存 | 每次改 `.py` 后必须删 `__pycache__` 再重启 Streamlit |
| API Key 持久化 | `.env` + `python-dotenv`，gitignore |
| 多模型切换 | `llm_configs.json` 持久化，前端面板增删切换 |
| 可变集数 | Prompt 全部 `{total_episodes}` 占位符，运行时 `fmt_*()` 填充 |
| 流式不阻塞 UI | 钩子标记 → st.empty() placeholder → st.rerun() 落位 |
| 对白批次 | 每批 `EPISODES_PER_BATCH=10` 集，逐 token 流式输出 |
| 分集失败回退 | 一次生成失败 → 自动降级为 `_generate_episodes_batched()` 分批 |
| 卡点保存 | 每个卡点确认时立即保存到剧名文件夹，不等到全部完成 |
| 前端编辑同步 | editor widget 使用版本号递增 key，禁止手动写 session_state |
