# siku 决策日志

更新时间：2026-06-17

## 文档定位

本文记录项目探索过程中已经讨论并确认的关键问题和决策。它采用轻量 ADR 格式，便于后续追加。

状态含义：

- `已实施`：代码或文档已经落地。
- `已确认`：需求和设计已确认，但可能尚未实施。
- `提案中`：已进入 OpenSpec 提案，但代码尚未实施。
- `延后`：明确不在当前阶段实施。

## D001 项目形态

问题：这个知识管理能力应该做成 Codex Skill、插件、Web 应用还是 CLI？

决策：做成 Python CLI，面向 Hermes agent 调用。

理由：Hermes 需要稳定的机器接口。CLI 的 stdin/stdout 契约清晰，易于测试、组合和部署。Codex Skill 更适合增强 Codex 自身能力，不适合作为 Hermes 长期调用的业务工具。

状态：已实施。

## D002 主调用协议

问题：CLI 应该用 shell flags 还是 JSON stdin/stdout？

决策：权威 agent 接口使用 JSON stdin/stdout。

理由：JSON 更适合 Hermes 传参和解析结构化错误。shell flags 未来可以作为人类便利包装，但不作为主协议。

状态：已实施。

## D003 单 URL 处理

问题：首版是否支持批处理？

决策：不支持批处理，每次只处理一个 URL。

理由：单 URL 更容易做幂等、重试、错误定位和 Hermes 调度。批量能力可以留给上层系统逐条调用。

状态：已实施。

## D004 全自动写入

问题：Obsidian 写入前是否需要人工确认？

决策：不需要人工确认，默认全自动写入。

理由：目标使用者是 Hermes agent，交互式确认会破坏自动化链路。安全边界通过配置校验、固定目录、结构化错误和受控 tools 实现。

状态：已实施。

## D005 输出语言

问题：总结、标题、标签和文档使用什么语言？

决策：用户可见文档和总结内容始终使用中文；代码标识、JSON 字段、错误码、路径和命令保持原文。

理由：知识库主要面向中文阅读和管理，同时协议字段需要保持稳定。

状态：已实施。

## D006 素材仓库位置

问题：原文、原视频、原始素材是否放入 Obsidian vault？

决策：原始素材保存在 Obsidian vault 外部的可配置素材仓库中。

理由：避免大文件污染 vault。Obsidian note 只引用原始链接和本地素材路径。

状态：已实施。

## D007 Obsidian note 内容边界

问题：Obsidian 正文是否包含完整原文或完整转写？

决策：不包含。正文只包含总结、原始链接和素材路径引用。

理由：Obsidian 用于知识管理，不作为原始素材仓库。完整内容留在素材仓库中。

状态：已实施。

## D008 索引技术选择

问题：索引文件记录在 JSON 文件中，知识越来越多后是否会有性能问题？

决策：使用 SQLite 作为长期索引，不使用单个 JSON 文件作为权威索引。

理由：SQLite 支持索引查找、事务写入、失败记录和未来查询扩展。单 JSON 文件随数据增长会读写成本高，也更容易出现并发和损坏问题。

状态：已实施。

## D009 `source_id` 生成

问题：如何稳定标识同一来源？

决策：使用 `sha256(normalized_url).hexdigest()` 作为 `source_id`。

理由：稳定、确定、无须数据库自增，也避免 URL 原文直接暴露到路径中。

状态：已实施。

## D010 URL 路由范围

问题：首版支持哪些内容类型？

决策：首版支持 `bilibili_video` 和 `web_article`，其他返回 `UNSUPPORTED_URL`。

理由：先覆盖 Bilibili 视频和文章两个核心场景，避免一次引入 PDF、播客、社交媒体等复杂来源。

状态：已实施。

## D011 Bilibili 策略

问题：Bilibili 视频如何生成文本？

决策：先下载元数据和字幕；如果没有字幕，再下载音频并用本地 Whisper 转写；最终输出规范文本。

理由：字幕成本低、速度快；无字幕时用 Whisper 保证闭环。

状态：已实施。

## D012 Bilibili 下载实现

问题：Bilibili 元数据和音频下载用什么技术？

决策：使用受控 `yt-dlp` wrapper。

理由：`yt-dlp` 是成熟下载工具，能处理视频站点复杂逻辑。项目层只封装命令、错误映射和输出解析。

状态：已实施。

## D013 Bilibili 412 调试结论

问题：Bilibili 通过 `yt-dlp` 获取元数据时出现 HTTP 412 怎么处理？

决策：参考 `/home/xu/workspace/hot_pulse` 的技术方案，给 `yt-dlp` 增加 Bilibili 需要的 `Referer`、`Origin` 和 User-Agent 请求头。

理由：直接浏览器 cookie 导出和 Edge cookie 解密在本地环境中不稳定。固定请求头方案更符合项目边界，也更易测试。

状态：已实施。

## D014 不依赖 hot_pulse 运行时路径

问题：能否直接复用 `/home/xu/workspace/hot_pulse` 的模型路径？

决策：不能直接依赖 hot_pulse 的模型路径，只参考实现思路。

理由：跨项目路径依赖会破坏当前项目边界。当前项目应根据自身配置下载或导出模型到自己的模型目录。

状态：已实施。

## D015 Whisper 加速方案

问题：Whisper 使用什么运行方式？

决策：使用 OpenVINO + optimum-intel，通过 Intel Xe 集成显卡本地加速。

理由：用户本地硬件是 Intel 集成显卡，目标是本地转写，不依赖远程 ASR。

状态：已实施。

## D016 Whisper CPU fallback

问题：GPU 不可用时是否静默回退到 CPU？

决策：不静默回退。`whisper.device = "CPU"` 被拒绝，运行时不可用返回 `WHISPER_UNAVAILABLE`。

理由：用户明确希望 Intel GPU 加速。静默 CPU fallback 会掩盖性能问题。

状态：已实施。

## D017 Whisper 模型目录

问题：Whisper 模型应该放在哪里？

决策：使用当前项目配置的 `whisper.model_dir`，默认 `models/whisper`，首次需要时下载或导出到该目录。

理由：避免依赖其他项目的模型路径，保证项目边界清晰。

状态：已实施。

## D018 Whisper 模型尺寸

问题：默认 Whisper 使用什么尺寸？

决策：默认 `medium`，可配置为 `tiny`、`small` 或 `medium`。

理由：`medium` 在质量和性能之间更均衡；调试时可用 `tiny` 快速验证 GPU 和音频链路。

状态：已实施。

## D019 网页解析范围

问题：不同来源网页布局不同，是否应该拆成专用 skill/parser？

决策：是。首期支持微信公众号专用 parser 和通用 fallback parser。

理由：微信公众号有稳定结构，专用 parser 能降低噪声；其他网页用成熟库兜底。

状态：已实施。

## D020 不做 Playwright fallback

问题：网页解析是否需要 Playwright/browser fallback？

决策：首期不做。

理由：浏览器依赖、登录态和动态网页会显著增加复杂度。先用普通 HTTP 和成熟解析库打通基础闭环。

状态：已实施。

## D021 通用网页解析库

问题：通用网页正文提取用什么方案？

决策：使用 `trafilatura`，配合 `httpx` 和 `beautifulsoup4`。

理由：这些库成熟、轻量，适合首期 fallback。

状态：已实施。

## D022 固定领域表

问题：领域分类是否让模型自由生成？

决策：只允许模型从固定领域表中选择一个主领域。

理由：固定领域表有利于标签一致性、prompt 选择和后续统计。自由分类会导致领域名漂移。

状态：已实施。

## D023 菜谱领域

问题：固定领域表是否需要加入 `菜谱`？

决策：加入 `菜谱`。

理由：菜谱有独立总结结构和长期知识价值，不适合混入生活类。

状态：已实施。

## D024 领域分类低置信度处理

问题：低置信度、跨领域或证据不足时怎么办？

决策：归入 `其他`，不因为低置信度而失败。

理由：分类失败会中断整个导入流程；归入 `其他` 更利于保持自动化闭环。

状态：已实施。

## D025 分类输入长度

问题：领域分类是否读取完整文本？

决策：分类 prompt 只使用规范文本前 12000 个字符。

理由：分类不需要完整长文，截断能控制成本和上下文长度。

状态：已实施。

## D026 模型定义方式

问题：每个任务如何选择不同大模型？

决策：在 `[llm.models.<ref>]` 集中定义模型，在 `[llm.tasks]` 中按任务引用模型。

理由：模型定义和任务使用解耦。不同环节可以引用不同模型，例如分类用 fast 模型，总结用 pro 模型。

状态：已实施。

## D027 供应商协议

问题：首版支持哪些 LLM provider？

决策：首版只支持 `provider = "openai_compatible"`。

理由：DeepSeek 和其他兼容 API 都可以纳入这一接口，先保持实现简单。

状态：已实施。

## D028 domain.json 字段

问题：`domain.json` 是否包含模型引用和模型名？

决策：包含 `model_ref` 和 `model`。

理由：方便追溯分类结果来自哪个模型定义和实际模型。

状态：已实施。

## D029 不生成 domain.md

问题：领域分类是否生成 Markdown 文件？

决策：不生成 `domain.md`，只生成 `summary/domain.json`。

理由：领域分类是中间结构化产物，不需要单独进入 Obsidian 阅读。

状态：已实施。

## D030 总结策略

问题：长文本是否按固定字符数切块，先生成 chunk summaries 再汇总？

决策：不采用切块汇总。长短文本都使用单次总结。

理由：降低复杂度。当前 DeepSeek V4 级别模型上下文较大，首版可以先不引入分块策略。

状态：已实施。

## D031 总结截断配置

问题：默认是否需要截断长文本？

决策：默认 `summary.max_input_chars = 0`，表示不主动截断；如果用户显式配置正整数才截断。

理由：模型上下文能力足够时不必过早损失信息。保留配置作为安全阀。

状态：已实施。

## D032 summary.json 作用

问题：`summary.json` 是什么？

决策：`summary.json` 是分析之后的权威结构化总结输出物。

理由：它是 Obsidian renderer 的输入，也是后续追溯、评测和重试的核心产物。

状态：已实施。

## D033 summary.json questions 字段

问题：`summary.json` 中的 `questions` 有什么作用？

决策：`questions` 表示模型基于内容提出的延伸思考问题或待追问问题。

理由：这些问题帮助后续复盘和主动学习，但系统不会自动回答或评测它们。

状态：已实施。

## D034 总结评测

问题：是否在总结阶段同时触发两个模型用于人工评测？

决策：支持配置化评测模式，同时调用多个候选模型。

理由：用户希望线下人工比较不同模型总结质量。系统只负责产出候选文件。

状态：已实施。

## D035 评测默认模型

问题：评测模式默认使用哪些模型？

决策：候选模型使用 `deepseek_v4_flash` 和 `deepseek_v4_pro` 这类模型引用名，主输出使用 `deepseek_v4_pro`。

理由：Flash 可作为速度和成本对照，Pro 作为权威总结更稳。代码只依赖模型引用名。

状态：已实施。

## D036 评测边界

问题：系统是否需要评分、排序或记录人工选择？

决策：不需要。评测完全线下人工完成。

理由：首版只需要生成候选结果，评分系统会增加额外复杂度。

状态：已实施。

## D037 Obsidian 组织方式

问题：Obsidian 笔记如何组织？

决策：写入 vault 内配置的 `inbox_dir`，采用 `YYYY-MM-DD-safe-title.md` 文件名。

理由：保持入口集中，后续用户可以在 Obsidian 内自行整理。

状态：已实施。

## D038 note 幂等覆盖

问题：同一来源重复处理时如何写 note？

决策：同 `source_id` 覆盖同一 note 并保留旧 `created_at`；不同来源同名时使用 `-<source_id前8位>` 兜底。

理由：保证重试幂等，同时避免不同来源互相覆盖。

状态：已实施。

## D039 processed 状态

问题：何时把 SQLite 标记为 `processed`？

决策：只有 Obsidian note 写入成功后，才写入或更新 SQLite `status = "processed"`。

理由：`processed` 表示端到端闭环完成，而不是只完成文本化或总结。

状态：已实施。

## D040 note 写入成功但 SQLite 失败

问题：note 已写入但 SQLite processed 写入失败怎么办？

决策：返回 `INDEX_WRITE_FAILED`，响应中包含 `note_path`，并尽量写入 failed 状态。

理由：方便后续重试和人工检查，不让已写出的 note 丢失线索。

状态：已实施。

## D041 项目管理工具

问题：是否使用 venv，还是使用其他项目管理工具？

决策：使用 uv 管理依赖、锁文件、命令运行和项目虚拟环境。

理由：uv 能统一 Python 版本、依赖解析、`uv.lock` 和 `.venv/` 管理。

状态：已实施。

## D042 uv 虚拟环境

问题：使用 uv 是否也管理 `.venv/`？

决策：是。`uv sync` 会创建和同步项目 `.venv/`。

理由：不需要手动维护传统 venv 流程。

状态：已实施。

## D043 `.env` 用法

问题：API key 如何持久化和激活？

决策：将环境变量写入 `.env`，运行时使用 `uv run --env-file .env ...`。

理由：API key 不进入代码或文档示例真实值，运行时由环境注入。

状态：已确认。

## D044 OpenSpec 工作流

问题：阶段研发如何组织？

决策：使用 OpenSpec 提案、spec、design、tasks 管理每个阶段。

理由：阶段边界清晰，提案可 review，可归档，可与实现任务绑定。

状态：已实施。

## D045 Superpowers 工作流

问题：开发时如何保证质量？

决策：使用 Superpowers 的 brainstorming、TDD、code review、systematic debugging 和 verification-before-completion 工作流。

理由：项目能力逐步变复杂，需要强制澄清、测试先行、审查和验证。

状态：已实施。

## D046 文档语言

问题：OpenSpec 和 Superpowers 文档用中文还是英文？

决策：全部项目文档默认用中文编写。

理由：项目知识和用户讨论主要使用中文，减少理解成本。

状态：已实施。

## D047 Git local

问题：是否使用 `git-local` 作为主要提交历史？

决策：不把 `git-local` 作为正式历史；项目最终应提交到真实 Git 仓库。

理由：项目刚开始时可以接受重新提交真实仓库历史，避免工具内部历史和真实 Git 历史混淆。

状态：已确认。

## D048 阶段拆分

问题：项目是否一次性做完，还是拆阶段？

决策：拆成阶段推进。已确认核心路线从 CLI 契约、本地状态、URL 路由、内容采集、领域分类、总结、Obsidian 写入到 Deep Agents 编排。

理由：每阶段可以独立提案、实现、测试和归档，风险更低。

状态：已实施。

## D049 Deep Agents 集成时机

问题：Deep Agents 什么时候集成？

决策：不在早期文本化阶段集成。先用确定性 Python pipeline 打通能力，阶段九再集成 Deep Agents 编排。

理由：先建立稳定 tools 和回归基线，再让 agent 编排，风险更低。

状态：提案中。

## D050 Hermes 与 Deep Agents 边界

问题：Hermes 是否直接编排 tool？

决策：不。Hermes 只调用 `km agent-ingest`，Deep Agents 在项目内部编排 tools。

理由：Hermes 需要稳定外部契约，项目内部负责状态机、trace、重试和工具边界。

状态：提案中。

## D051 `km ingest` 与 `km agent-ingest`

问题：是否用一个命令加参数切换编排器？

决策：新增独立命令 `km agent-ingest`，保留 `km ingest` 确定性路径。

理由：两个入口边界清晰，现有稳定契约不被阶段九影响。

状态：提案中。

## D052 agent 路径失败处理

问题：`km agent-ingest` 失败时是否自动 fallback 到 `km ingest`？

决策：不自动 fallback。

理由：fallback 会掩盖 agent 编排问题。失败应明确暴露为 agent 路径失败。

状态：提案中。

## D053 Deep Agents tool 粒度

问题：agent tools 应该细粒度还是中等粒度？

决策：使用中等粒度 tools。

理由：Deep Agents 负责阶段选择，不负责 Bilibili 内部下载细节。中等粒度能减少 token 和错误空间。

状态：提案中。

## D054 agent 状态机 guard

问题：仅靠 prompt 能否限制 agent 调用顺序？

决策：不能。必须使用 Python 状态机 guard 强制合法转换。

理由：prompt 不是安全边界。状态机可以阻止错误 stage 的副作用。

状态：提案中。

## D055 agent state/trace 位置

问题：agent 编排状态放 SQLite 还是文件？

决策：放在素材目录下的 `agent/state.json` 和 `agent/trace.jsonl`。

理由：agent 编排状态属于运行过程细节，和单个素材强绑定。SQLite 继续只记录最终业务状态。

状态：提案中。

## D056 agent trace 隐私边界

问题：trace 是否记录完整内容和模型输出？

决策：不记录完整 transcript、正文、HTML、prompt、模型输出、API key、cookie 或环境变量值。

理由：trace 用于观察流程，不应泄露原始内容和秘密。

状态：提案中。

## D057 agent 产物复用

问题：`km agent-ingest` 重试时是否重新执行所有步骤？

决策：默认复用已有合法产物，不支持 `force`。

理由：节省下载、Whisper 和 LLM 成本。`force` 会引入级联失效规则，首版延后。

状态：提案中。

## D058 agent 重试策略

问题：agent 是否自动重试失败 tool？

决策：只对网络、API 和下载类可恢复错误最多重试一次；schema、配置、本地 runtime、Whisper、写入和非法转换错误不重试。

理由：可恢复瞬时错误值得重试；确定性错误重试没有意义，还会放大副作用风险。

状态：提案中。

## D059 AgentRuntime 适配层

问题：业务入口是否直接依赖 Deep Agents 框架 API？

决策：不直接依赖。新增 `AgentRuntime` 适配层，生产用 `DeepAgentsRuntime`，测试用 `FakeAgentRuntime`。

理由：隔离框架 API 变化，让默认测试不依赖真实 runtime、网络或远程模型。

状态：提案中。

## D060 agent optional extra

问题：Deep Agents runtime 是否放入默认依赖？

决策：放入 `agent` optional extra。

理由：默认 `uv sync` 不应要求安装 agent runtime；只有使用 `km agent-ingest` 时才需要。

状态：提案中。

## D061 agent 编排模型

问题：Deep Agents 编排模型如何配置？

决策：新增 `[llm.tasks] agent_orchestration = "<model_ref>"`，推荐使用 `deepseek_v4_flash`。

理由：编排任务主要是选择下一步 tool，状态机已限制空间，Flash 足够且成本更低。

状态：提案中。

## D062 agent 最大步骤数

问题：如何防止 agent 无限循环？

决策：固定 `max_tool_steps = 12`。

理由：正常路径约 7 个工具调用，12 能容纳一次重试和少量误判，同时防止无限循环。

状态：提案中。

## D063 skill loader

问题：Deep Agents 如何使用项目内 skills？

决策：`km agent-ingest` 启动时读取必需 `skills/*.md` 作为指令资产；缺失或空文件返回 `AGENT_SKILL_MISSING`。

理由：skills 是编排说明，不是执行权限。缺失时不应启动 agent。

状态：提案中。

## D064 Deep Agents 默认测试

问题：默认测试是否依赖真实 Deep Agents？

决策：不依赖。默认测试使用 `FakeAgentRuntime`，真实 Deep Agents 只做手动或可选集成验证。

理由：单元测试必须稳定、快速、离线。

状态：提案中。

## D065 阶段九响应字段

问题：`km agent-ingest` 的 stdout 是否要暴露 agent 可观察信息？

决策：在现有 envelope 基础上增加 `orchestrator`、`trace_path` 和 `state_path`。

理由：自动模式需要可调试，但不暴露内部完整内容。

状态：提案中。

## D066 Bilibili Cookie 处理

问题：是否依赖浏览器 Edge cookie 读取？

决策：不作为默认方案。

理由：本地 Edge cookie 解密受 keyring 和浏览器存储影响，调试中出现不可解密问题。默认实现更倾向受控请求头和可测试下载器封装。

状态：已确认。

## D067 stdout 噪音处理

问题：Whisper 或 transformers 的警告是否允许污染 stdout？

决策：不允许。CLI stdout 必须只输出最终 JSON object，噪音应进入 stderr 或被抑制。

理由：Hermes 需要稳定解析 stdout。

状态：已实施。

## D068 当前文档体系

问题：项目探索内容放在哪里？

决策：新增 `docs/project-overview.md` 和 `docs/decision-log.md`，README 只保留入口链接和运行说明。

理由：总览、决策历史和使用说明职责分离，便于长期维护。

状态：已实施。
