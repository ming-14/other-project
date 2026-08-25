/**
 * Gemini -> OpenAI 协议转换代理
 * 用途：让 Gemini CLI（发 /v1beta/models/{model}:generateContent）能调用
 *      OpenAI 兼容端点（如 https://api.openai.com/v1/chat/completions）。
 * 零依赖，仅用 Node 原生 http 模块。
 *
 * 用法：
 *   node proxy.mjs
 *   # 环境变量（可省略，默认值见下）：
 *   PORT=8787 UPSTREAM_URL=https://api.openai.com/v1/chat/completions \
 *   UPSTREAM_KEY=sk-xxx MODEL=gpt-4o-mini
 */
import http from 'node:http';
import https from 'node:https';
import fs from 'node:fs';
import path from 'node:path';

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || '127.0.0.1';
const UPSTREAM_URL = process.env.UPSTREAM_URL || 'https://api.openai.com/v1/chat/completions';
const UPSTREAM_KEY = process.env.UPSTREAM_KEY || '';
const MODEL = process.env.MODEL || 'gpt-4o-mini';

if (!UPSTREAM_KEY) {
  console.error('ERROR: UPSTREAM_KEY environment variable is required (set it to your OpenAI-compatible API key).');
  process.exit(1);
}

const upstream = new URL(UPSTREAM_URL);

// Gemini CLI 工具的真实参数 schema（CLI 发请求时 tools 定义里 properties 为空，
// 部分 OpenAI 兼容模型看不到正确参数名，只能猜 path/file 等；这里补全并做响应侧适配）
const TOOL_PARAM_SCHEMAS = {
  // 目录类
  list_directory: { dir_path: { type: 'string', description: 'Directory path to list' } },
  read_folder: { dir_path: { type: 'string', description: 'Directory path to read' } },
  ReadFolder: { dir_path: { type: 'string', description: 'Directory path to read' } },
  ls: { dir_path: { type: 'string', description: 'Directory path to list' } },
  // 文件读写
  read_file: { file_path: { type: 'string', description: 'Path to the file to read' } },
  read_files: { file_path: { type: 'string', description: 'Path to the file to read' } },
  read_many_files: { file_path: { type: 'string', description: 'Path to the file to read' } },
  write_file: {
    file_path: { type: 'string', description: 'Path of the file to write' },
    content: { type: 'string', description: 'Content to write' },
  },
  // 编辑
  edit: {
    file_path: { type: 'string', description: 'Path of the file to edit' },
    old_string: { type: 'string', description: 'Exact text to replace' },
    new_string: { type: 'string', description: 'Replacement text' },
    instruction: { type: 'string', description: 'A clear, semantic instruction for the code change, explaining why and what to change' },
  },
  replace: {
    file_path: { type: 'string', description: 'Path of the file to edit' },
    old_string: { type: 'string', description: 'Exact text to replace' },
    new_string: { type: 'string', description: 'Replacement text' },
    instruction: { type: 'string', description: 'A clear, semantic instruction for the code change, explaining why and what to change' },
  },
  // 搜索
  grep_search: {
    pattern: { type: 'string', description: 'Regular expression to search for' },
    dir_path: { type: 'string', description: 'Directory to search in' },
    include_pattern: { type: 'string', description: 'File glob filter' },
  },
  grep: {
    pattern: { type: 'string', description: 'Regular expression to search for' },
    dir_path: { type: 'string', description: 'Directory to search in' },
  },
  glob: {
    pattern: { type: 'string', description: 'Glob pattern to match' },
    dir_path: { type: 'string', description: 'Directory to search in' },
  },
  // shell
  run_shell_command: {
    command: { type: 'string', description: 'Command to execute' },
    dir_path: { type: 'string', description: 'Working directory' },
  },
  shell: {
    command: { type: 'string', description: 'Command to execute' },
    dir_path: { type: 'string', description: 'Working directory' },
  },
  // web fetch: URL 必须嵌入 prompt 里（CLI 从 prompt 提取 URL，不读 url 参数）
  web_fetch: {
    prompt: { type: 'string', description: 'Prompt containing the URL(s) to fetch (must include http:// or https:// URLs) and instructions for processing them' },
  },
  // 向用户提问
  ask_user: {
    questions: {
      type: 'array',
      description: 'Array of questions to ask the user',
      items: {
        type: 'object',
        properties: {
          question: { type: 'string', description: 'The question text' },
          type: { type: 'string', description: 'Question type: "text" or "choice"' },
          header: { type: 'string', description: 'Optional header' },
          options: {
            type: 'array',
            description: 'Options for choice type questions',
            items: {
              type: 'object',
              properties: {
                label: { type: 'string', description: 'Option label' },
                description: { type: 'string', description: 'Optional option description' },
              },
              required: ['label'],
            },
          },
        },
        required: ['question', 'type'],
      },
    },
  },
  // 联网搜索
  google_web_search: {
    query: { type: 'string', description: 'The search query to find information on the web' },
  },
  web_search: {
    query: { type: 'string', description: 'The search query to find information on the web' },
  },
  // 激活技能
  activate_skill: {
    name: { type: 'string', description: 'The name of the skill to activate' },
  },
  // 计划模式
  enter_plan_mode: {
    reason: { type: 'string', description: 'Short reason explaining why you are entering plan mode' },
  },
  // 退出计划模式（需要 plan_filename，代理会自动在 plans 目录创建占位文件）
  exit_plan_mode: {
    plan_filename: { type: 'string', description: 'The filename of the finalized plan (e.g., "plan.md"). Do not provide an absolute path.' },
  },
  // 调用子代理
  invoke_agent: {
    agent_name: { type: 'string', description: 'Name of the subagent to invoke' },
    prompt: { type: 'string', description: 'The COMPLETE query to send the subagent. MUST be comprehensive and detailed. Include all context, background, questions, and expected output format.' },
  },
  // 子代理完成任务（返回结果给主代理）
  complete_task: {
    result: { type: 'string', description: 'Your final results or findings to return to the orchestrator. This is the ONLY way to finish the task.' },
  },
  // 读取后台进程输出（需要 PID）
  read_background_output: {
    pid: { type: 'integer', description: 'The process ID (PID) of the background process to inspect.' },
    lines: { type: 'integer', description: 'Number of lines to read from the end of the log. Defaults to 100.' },
  },
  // 子代理报告（部分子代理用 report 返回结构化结果）
  report: {
    report: { type: 'object', description: 'The structured report object with your findings' },
  },
};

// 模型常猜的参数别名 -> 正确参数名（响应侧兜底映射）
const TOOL_PARAM_ALIASES = {
  list_directory: { path: 'dir_path', dir: 'dir_path', directory: 'dir_path', folder: 'dir_path' },
  read_folder: { path: 'dir_path', dir: 'dir_path', directory: 'dir_path', folder: 'dir_path' },
  ReadFolder: { path: 'dir_path', dir: 'dir_path', directory: 'dir_path', folder: 'dir_path' },
  ls: { path: 'dir_path', dir: 'dir_path', directory: 'dir_path', folder: 'dir_path' },
  read_file: { path: 'file_path', file: 'file_path', filename: 'file_path' },
  read_files: { path: 'file_path', file: 'file_path', filename: 'file_path' },
  read_many_files: { path: 'file_path', file: 'file_path', filename: 'file_path' },
  write_file: { path: 'file_path', file: 'file_path', filename: 'file_path' },
  edit: { path: 'file_path', file: 'file_path', oldText: 'old_string', newText: 'new_string' },
  replace: { path: 'file_path', file: 'file_path', oldText: 'old_string', newText: 'new_string' },
  grep_search: { query: 'pattern', regex: 'pattern', path: 'dir_path', dir: 'dir_path' },
  grep: { query: 'pattern', regex: 'pattern', path: 'dir_path', dir: 'dir_path' },
  glob: { path: 'dir_path', dir: 'dir_path' },
  run_shell_command: { cmd: 'command', path: 'dir_path', dir: 'dir_path', cwd: 'dir_path' },
  shell: { cmd: 'command', path: 'dir_path', dir: 'dir_path', cwd: 'dir_path' },
  // WebFetch：模型常把 URL 放进 urls/url，但 CLI 工具要求 URL 内嵌在 prompt 里
  web_fetch: { urls: 'prompt', url: 'prompt' },
  google_web_search: { q: 'query', search: 'query', prompt: 'query' },
  web_search: { q: 'query', search: 'query', prompt: 'query' },
  // AskUser：模型常传 question（单数对象/字符串），CLI 工具要求 questions 数组
  ask_user: { question: 'questions' },
  // 激活技能：模型常传 skill/技能名
  activate_skill: { skill: 'name', skill_name: 'name', skillName: 'name' },
  // 计划模式
  enter_plan_mode: { why: 'reason', description: 'reason', rationale: 'reason' },
  // 退出计划模式：模型常传空参数，自动补 plan_filename + 预先创建文件
  exit_plan_mode: { plan: 'plan_filename', filename: 'plan_filename', file: 'plan_filename' },
  // 子代理：模型常传 agent 别名
  invoke_agent: { agent: 'agent_name', subagent: 'agent_name', subagent_name: 'agent_name', query: 'prompt' },
  // 子代理完成：模型常传 summary/findings/answer；answer 不映射（可能是 report 内容）
  complete_task: { summary: 'result', findings: 'result', text: 'result', output: 'result', final_answer: 'result' },
  report: { data: 'report', findings: 'report', output: 'report' },
  // 后台输出：模型常传 process_id/path/pid 字符串
  read_background_output: { process_id: 'pid', processId: 'pid', process: 'pid', path: 'pid' },
};

/** 响应侧：把模型返回的 functionCall 参数名映射为 CLI 工具期望的参数名 */
function adaptToolArgs(toolName, args) {
  if (!args || typeof args !== 'object') return args || {};
  const aliasMap = TOOL_PARAM_ALIASES[toolName];
  if (!aliasMap) return args;
  const adapted = { ...args };
  for (const [alias, realName] of Object.entries(aliasMap)) {
    if (adapted[alias] !== undefined && adapted[realName] === undefined) {
      adapted[realName] = adapted[alias];
      delete adapted[alias];
    }
  }
  // WebFetch 特化：把 urls/url 合并进 prompt，让 CLI 工具能识别 URL
  if (toolName === 'web_fetch') {
    let urls = adapted.urls;
    delete adapted.urls;
    let url = adapted.url;
    delete adapted.url;
    let prompt = adapted.prompt || '';
    const urlParts = [];
    if (urls !== undefined) {
      let list = [];
      if (Array.isArray(urls)) list = urls;
      else if (typeof urls === 'string') {
        try {
          const parsed = JSON.parse(urls);
          list = Array.isArray(parsed) ? parsed : [urls];
        } catch {
          list = [urls];
        }
      }
      urlParts.push(...list.filter((u) => typeof u === 'string'));
    }
    if (typeof url === 'string' && url) urlParts.push(url);
    // 只保留合法 URL，且 prompt 里尚未包含的
    const validUrls = urlParts.filter((u) => /^https?:\/\//.test(u));
    if (validUrls.length) {
      const missing = validUrls.filter((u) => !prompt.includes(u));
      if (missing.length) {
        adapted.prompt = `${missing.join(' ')}\n${prompt}`.trim();
      } else {
        adapted.prompt = prompt;
      }
    } else {
      adapted.prompt = prompt;
    }
  }
  // Edit/Replace 特化：缺 instruction 时生成一个
  if ((toolName === 'edit' || toolName === 'replace') && !adapted.instruction) {
    const summary = adapted.new_string?.slice(0, 80) || '';
    adapted.instruction = `Apply the change to ${adapted.file_path || 'the file'} by replacing the old text with the new text${summary ? ` (new text: "${summary}...")` : ''}.`;
  }
  // AskUser 特化：question 不是数组时包装成 questions 数组；options 元素 text -> label
  if (toolName === 'ask_user') {
    if (adapted.questions !== undefined && !Array.isArray(adapted.questions)) {
      adapted.questions = [adapted.questions];
    }
    if (Array.isArray(adapted.questions)) {
      adapted.questions = adapted.questions.map((q) => {
        if (!q || typeof q !== 'object') return q;
        const nq = { ...q };
        if (Array.isArray(nq.options)) {
          nq.options = nq.options.map((opt) => {
            if (typeof opt === 'string') return { label: opt, description: opt };
            if (opt && typeof opt === 'object') {
              const no = { ...opt };
              if (no.label === undefined && no.text !== undefined) {
                no.label = no.text;
                delete no.text;
              }
              if (no.description === undefined) no.description = no.label || '';
              return no;
            }
            return opt;
          });
        }
        return nq;
      });
    }
  }
  // activate_skill：缺 name 时不调用（无法猜测），保持原样（模型下次会带）
  // enter_plan_mode：缺 reason 时生成默认
  if (toolName === 'enter_plan_mode' && !adapted.reason) {
    adapted.reason = 'Entering plan mode to safely research and design the requested change.';
  }
  // Shell：is_background 应为布尔（模型常传字符串）
  if (toolName === 'run_shell_command' || toolName === 'shell') {
    if (adapted.is_background !== undefined) {
      const v = String(adapted.is_background).toLowerCase();
      adapted.is_background = v === 'true' || v === '1' || v === 'yes';
    }
    if (adapted.isBackground !== undefined && adapted.is_background === undefined) {
      const v = String(adapted.isBackground).toLowerCase();
      adapted.is_background = v === 'true' || v === '1' || v === 'yes';
      delete adapted.isBackground;
    }
  }
  // read_file / read_background_output：数值参数转整数
  if (toolName === 'read_file' || toolName === 'read_files' || toolName === 'read_many_files') {
    for (const key of ['start_line', 'end_line', 'offset', 'limit']) {
      if (adapted[key] !== undefined) {
        const n = Number(adapted[key]);
        if (!Number.isNaN(n)) adapted[key] = n;
      }
    }
  }
  if (toolName === 'read_background_output' && adapted.pid !== undefined) {
    const n = Number(adapted.pid);
    if (!Number.isNaN(n)) adapted.pid = n;
  }
  // exit_plan_mode：缺 plan_filename 时补默认（代理已确保 plan.md 存在于 plans 目录）
  if (toolName === 'exit_plan_mode' && !adapted.plan_filename) {
    adapted.plan_filename = 'plan.md';
  }
  // complete_task 特化：report/result 若是 JSON 字符串，解析成对象（CLI 子代理要求对象）
  if (toolName === 'complete_task') {
    for (const key of ['report', 'result']) {
      const v = adapted[key];
      if (typeof v === 'string' && v.trim().startsWith('{')) {
        try {
          adapted[key] = JSON.parse(v);
        } catch { /* keep as string */ }
      }
    }
    // 若模型只传了 result 而 CLI 要 report（子代理场景），用 result 填充 report
    if (adapted.report === undefined && adapted.result !== undefined) {
      adapted.report = adapted.result;
      delete adapted.result;
    }
  }
  return adapted;
}

function log(...args) {
  console.log(new Date().toISOString(), ...args);
}

/** Gemini GenerateContent 请求体 -> OpenAI ChatCompletion 请求体 */
function geminiToOpenAI(geminiReq, stream = false) {
  const messages = [];
  const systemInstruction = geminiReq.systemInstruction;
  if (systemInstruction) {
    const text = (systemInstruction.parts || [])
      .map((p) => p.text || '')
      .join('');
    if (text) messages.push({ role: 'system', content: text });
  }
  for (const c of geminiReq.contents || []) {
    const role = c.role === 'model' ? 'assistant' : c.role === 'user' ? 'user' : c.role || 'user';
    const text = (c.parts || [])
      .map((p) => {
        if (p.text !== undefined) return p.text;
        if (p.functionCall) return `[function_call: ${p.functionCall.name}] ${JSON.stringify(p.functionCall.args || {})}`;
        if (p.functionResponse) return `[function_result: ${p.functionResponse.name}] ${JSON.stringify(p.functionResponse.response || {})}`;
        if (p.inlineData) return `[image data omitted: ${p.inlineData.mimeType}]`;
        return '';
      })
      .join('');
    messages.push({ role, content: text });
  }

  const g = geminiReq.generationConfig || {};
  const body = {
    model: MODEL,
    messages,
  };
  if (g.temperature !== undefined) body.temperature = g.temperature;
  if (g.topP !== undefined) body.top_p = g.topP;
  if (g.topK !== undefined) body.top_k = g.topK;
  if (g.maxOutputTokens !== undefined) body.max_tokens = g.maxOutputTokens;
  if (g.stopSequences?.length) body.stop = g.stopSequences;
  if (stream) body.stream = true;

  if (geminiReq.tools?.length) {
    const functions = [];
    for (const tool of geminiReq.tools) {
      for (const fn of tool.functionDeclarations || []) {
        // 补全参数 schema：CLI 发的 properties 为空，模型看不到参数名。
        // 已知工具用内置 schema；若 CLI 已提供非空 properties（如 complete_task 的 report/result 对象），保留原始。
        let parameters = fn.parameters;
        const existingProps = parameters?.properties;
        const hasProps = existingProps && Object.keys(existingProps).length > 0;
        const known = TOOL_PARAM_SCHEMAS[fn.name];
        if (known && !hasProps) {
          parameters = {
            type: 'object',
            properties: { ...known },
            required: [...Object.keys(known)],
          };
        } else if (!parameters) {
          parameters = { type: 'object', properties: {} };
        }
        functions.push({
          type: 'function',
          function: {
            name: fn.name,
            description: fn.description || '',
            parameters,
          },
        });
      }
    }
    if (functions.length) body.tools = functions;
  }
  return body;
}

/** OpenAI ChatCompletion 响应体 -> Gemini GenerateContent 响应体 */
function openAIToGemini(oai) {
  const candidates = (oai.choices || []).map((ch) => {
    const msg = ch.message || {};
    const parts = [];
    if (msg.content) parts.push({ text: msg.content });
    // 部分后端会返回 reasoning 字段，可作为 thinking 展示
    const reasoning = msg.reasoning || msg.reasoning_content;
    if (reasoning && reasoning !== msg.content) {
      parts.push({ thought: true, text: reasoning });
    }
    if (msg.tool_calls?.length) {
      for (const tc of msg.tool_calls) {
        const rawArgs = (() => {
          try {
            return JSON.parse(tc.function?.arguments || '{}');
          } catch {
            return {};
          }
        })();
        parts.push({
          functionCall: {
            name: tc.function?.name || '',
            args: adaptToolArgs(tc.function?.name || '', rawArgs),
          },
        });
      }
    }
    const finishMap = { stop: 'STOP', length: 'MAX_TOKENS', tool_calls: 'STOP' };
    return {
      content: { role: 'model', parts },
      finishReason: finishMap[ch.finish_reason] || 'STOP',
      index: ch.index ?? 0,
    };
  });
  const u = oai.usage || {};
  const resp = {
    candidates,
    usageMetadata: {
      promptTokenCount: u.prompt_tokens ?? 0,
      candidatesTokenCount: u.completion_tokens ?? 0,
      totalTokenCount: u.total_tokens ?? 0,
    },
    modelVersion: oai.model || MODEL,
  };
  return resp;
}

/** 解析模型把工具调用放在 content 文本里的格式（部分 OpenAI 兼容后端常见行为）：
 * 1. `[function_call: name] {"arg":"val"}[function_call: name2] {...}`
 * 2. `[function_call=name] <parameter name="x">val</parameter>...</function>`
 * 返回 [{name, args}] 或 null
 */
function parseInlineFunctionCalls(content) {
  if (!content || typeof content !== 'string') return null;
  const calls = [];
  let text = content.trim();

  // 模式 1：JSON 风格 [function_call: name] {...}
  const jsonRe = /\[function_call:\s*([A-Za-z_][A-Za-z0-9_]*)\]\s*(\{[^{}]*\})/g;
  let jsonMatch;
  while ((jsonMatch = jsonRe.exec(text)) !== null) {
    try {
      calls.push({ name: jsonMatch[1], args: JSON.parse(jsonMatch[2]) });
    } catch { /* skip */ }
  }
  // 检查是否整个文本都是 JSON 调用序列（中间夹杂少量普通文本也可）
  const jsonOnly = text.replace(jsonRe, '').trim();
  if (calls.length > 0 && jsonOnly.length === 0) {
    return calls;
  }

  // 模式 2：XML 风格 [function_call:name] 或 [function_call=name] <parameter ...>...</function>
  const xmlRe = /\[function_call[:=]\s*([A-Za-z_][A-Za-z0-9_]*)\]([\s\S]*?)(?:<\/function>|$)/;
  const xmlMatch = xmlRe.exec(text);
  if (xmlMatch) {
    const name = xmlMatch[1];
    const body = xmlMatch[2];
    const args = {};
    // 支持 <parameter name="x">val</parameter> 和 <parameter=x>val</parameter>
    const paramRe = /<parameter\s+(?:name\s*=\s*"([^"]+)"|([A-Za-z0-9_]+))\s*>([\s\S]*?)<\/parameter>/g;
    let pm;
    while ((pm = paramRe.exec(body)) !== null) {
      const key = pm[1] || pm[2];
      if (key) args[key] = pm[3].trim();
    }
    if (Object.keys(args).length > 0 || /<parameter/i.test(body)) {
      calls.push({ name, args });
      return calls;
    }
  }

  return calls.length > 0 ? calls : null;
}

/** 把 content 文本里的内联函数调用转成 Gemini functionCall parts（无则返回 null） */
function inlineCallsToParts(content) {
  const calls = parseInlineFunctionCalls(content);
  if (!calls) return null;
  return calls.map((c) => ({
    functionCall: {
      name: c.name,
      args: adaptToolArgs(c.name, c.args),
    },
  }));
}

/** OpenAI 流式 SSE chunk -> Gemini 流式 chunk（保持 OpenAI 原始格式也行，此处转成 Gemini） */
function openAIStreamChunkToGemini(rawJson) {
  if (!rawJson || rawJson === '[DONE]') return null;
  let oai;
  try {
    oai = JSON.parse(rawJson);
  } catch {
    return null;
  }
  const deltas = (oai.choices || []).map((ch) => {
    const d = ch.delta || {};
    const parts = [];
    if (d.content) parts.push({ text: d.content });
    // 兼容不同后端的思考字段：OpenAI 标准 reasoning_content、部分兼容后端的 reasoning
    const reasoning = d.reasoning_content || d.reasoning;
    if (reasoning) parts.push({ thought: true, text: reasoning });
    const finishMap = { stop: 'STOP', length: 'MAX_TOKENS', tool_calls: 'STOP' };
    return {
      content: { role: 'model', parts },
      finishReason: finishMap[ch.finish_reason] || null,
      index: ch.index ?? 0,
    };
  });
  const chunk = { candidates: deltas };
  if (oai.usage) {
    chunk.usageMetadata = {
      promptTokenCount: oai.usage.prompt_tokens ?? 0,
      candidatesTokenCount: oai.usage.completion_tokens ?? 0,
      totalTokenCount: oai.usage.total_tokens ?? 0,
    };
  }
  return chunk;
}

function sendJson(res, status, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body),
  });
  res.end(body);
}

function sendSse(res, obj) {
  res.write(`data: ${JSON.stringify(obj)}\n\n`);
}

/** 上游 token 上限（按 262144 上下文预留余量）。 */
const MAX_PROMPT_TOKENS = 220000;
const EST_CHARS_PER_TOKEN = 3.5;

/**
 * 请求体过大时截断历史：始终保留 system 与最近 2 条消息，
 * 对超长的中间消息（巨型工具结果）逐个截短，直到总量降到上限内。
 */
function truncateBody(body, maxTokens = MAX_PROMPT_TOKENS) {
  if (!body?.messages?.length) return body;
  const estimate = (s) => Math.ceil((s?.length || 0) / EST_CHARS_PER_TOKEN) + 8;
  let total = body.messages.reduce((sum, m) => sum + estimate(m.content), 0);
  if (total <= maxTokens) return body;

  log(`TRUNCATE: estimated ${total} tokens > ${maxTokens}, trimming history`);
  // 头部：system（若有）；尾部：仅最近 1 条（最新用户消息）
  const head = body.messages.slice(0, 1);
  const tail = body.messages.slice(-1);
  const middle = body.messages.slice(1, -1);

  // 按内容长度降序，先截最长的
  const idxBySize = middle
    .map((m, i) => ({ i, len: m.content?.length || 0 }))
    .sort((a, b) => b.len - a.len);

  const trimmed = middle.map((m) => ({ ...m }));
  const CHAR_BUDGET = 6000; // 单条消息截断后的最大字符数（约 1700 token）
  for (const { i, len } of idxBySize) {
    if (total <= maxTokens) break;
    const est = estimate(trimmed[i].content);
    if (len > CHAR_BUDGET) {
      const kept = trimmed[i].content.slice(0, CHAR_BUDGET);
      total = total - est + estimate(kept) + 2;
      trimmed[i].content = `${kept}\n...[truncated by proxy: was ~${len} chars]`;
    } else {
      // 截到 CHAR_BUDGET 仍超限的中等消息：整个替换为摘要
      total = total - est + 3;
      trimmed[i].content = '[truncated tool output removed by proxy]';
    }
  }

  // 若仍超限（极端情况），进一步把尾部之前的所有中间消息摘要化
  if (total > maxTokens) {
    for (const m of trimmed) {
      if (total <= maxTokens) break;
      const est = estimate(m.content);
      if (m.content?.length > 200) {
        total = total - est + 3;
        m.content = '[truncated tool output removed by proxy]';
      }
    }
  }

  // 兜底：连最后一条用户消息都超大时（如最后一条是工具结果），截断它
  if (total > maxTokens) {
    const last = tail[0];
    if (last && (last.content?.length || 0) > CHAR_BUDGET) {
      const est = estimate(last.content);
      const kept = last.content.slice(0, CHAR_BUDGET);
      total = total - est + estimate(kept) + 2;
      tail[0] = { ...last, content: `${kept}\n...[truncated by proxy]` };
      log(`TRUNCATE: last message also trimmed (${est} -> ~${estimate(kept)} tokens)`);
    }
  }

  return { ...body, messages: [...head, ...trimmed, ...tail] };
}

/** 从 Gemini 请求体中解析项目的临时目录（session_context 里声明） */
let cachedTempDir = null;
function getTempDirFromRequest(geminiReq) {
  if (cachedTempDir) return cachedTempDir;
  try {
    const marker = "The project's temporary directory is:";
    const raw = JSON.stringify(geminiReq);
    const idx = raw.indexOf(marker);
    if (idx !== -1) {
      let rest = raw.slice(idx + marker.length);
      rest = rest.replace(/^[:\s]+/, '');
      // JSON.stringify 把 \ 变成 \\，换行变 \\n；路径到第一个 \\n（或未转义引号）为止
      const m = rest.match(/^([^"\\]*(?:\\\\[^"\\]*)*)(?=\\n|")/);
      let dir = m ? m[1].trim() : null;
      if (dir) {
        dir = dir.replace(/\\\\/g, '\\');
        cachedTempDir = dir;
        log('PROJECT TEMP DIR found in request (path not logged)');
      }
    }
  } catch { /* ignore */ }
  return cachedTempDir;
}

/** 确保 plans 目录存在并创建 plan 文件（CLI 的 exit_plan_mode 要求文件已存在） */
function ensurePlanFile(tempDir) {
  if (!tempDir) return null;
  try {
    const plansDir = path.join(tempDir, 'plans');
    fs.mkdirSync(plansDir, { recursive: true });
    const planPath = path.join(plansDir, 'plan.md');
    if (!fs.existsSync(planPath)) {
      fs.writeFileSync(
        planPath,
        '# Plan\n\n(Plan file auto-created by proxy so exit_plan_mode can complete.)\n',
        'utf-8',
      );
    }
    return 'plan.md';
  } catch (e) {
    log('ENSURE PLAN FILE ERROR', e.message);
    return null;
  }
}

function requestUpstream(bodyJson, { stream } = {}) {
  return new Promise((resolve, reject) => {
    const client = upstream.protocol === 'https:' ? https : http;
    const req = client.request(
      {
        hostname: upstream.hostname,
        port: upstream.port || (upstream.protocol === 'https:' ? 443 : 80),
        path: upstream.pathname,
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${UPSTREAM_KEY}`,
          'Content-Length': Buffer.byteLength(bodyJson),
        },
        agent: undefined,
      },
      (res) => {
        if (stream) {
          resolve(res);
          return;
        }
        let data = '';
        res.on('data', (c) => (data += c));
        res.on('end', () => resolve({ status: res.statusCode, data }));
      },
    );
    req.on('error', reject);
    req.write(bodyJson);
    req.end();
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  // GET /v1beta/models —— 简单返回模型列表，避免 CLI 报 404
  if (req.method === 'GET' && path === '/v1beta/models') {
    sendJson(res, 200, {
      models: [{ name: `models/${MODEL}`, displayName: MODEL }],
    });
    return;
  }

  // POST /v1beta/models/{model}:countTokens —— 简单返回估算值（CLI 用于上下文管理）
  const ct = path.match(/^\/v1beta\/models\/([^:]+):countTokens$/);
  if (req.method === 'POST' && ct) {
    let raw = '';
    for await (const c of req) raw += c;
    let req2;
    try {
      req2 = JSON.parse(raw || '{}');
    } catch {
      sendJson(res, 400, { error: { code: 400, message: 'Bad JSON body' } });
      return;
    }
    const text = (req2.contents || [])
      .flatMap((c) => (c.parts || []).map((p) => p.text || ''))
      .join(' ');
    // 粗略估算：中文约 1 token/字符，英文约 4 字符/token
    const totalTokens = Math.ceil(text.length * 0.7) + 64;
    log(`countTokens model=${ct[1]} estimated=${totalTokens}`);
    sendJson(res, 200, { totalTokens });
    return;
  }

  // POST /v1beta/models/{model}:generateContent 或 :streamGenerateContent
  const m = path.match(/^\/v1beta\/models\/([^:]+):(generateContent|streamGenerateContent)$/);
  if (req.method === 'POST' && m) {
    let raw = '';
    for await (const c of req) raw += c;
    let geminiReq;
    try {
      geminiReq = JSON.parse(raw || '{}');
    } catch {
      sendJson(res, 400, { error: { code: 400, message: 'Bad JSON body' } });
      return;
    }

    const tempDir = getTempDirFromRequest(geminiReq);
    if (tempDir) {
      // 扫描请求中的 functionCall，若模型在调 exit_plan_mode 而 plan 文件不存在，先创建
      const allCalls = JSON.stringify(geminiReq);
      if (allCalls.includes('exit_plan_mode')) {
        ensurePlanFile(tempDir);
      }
    }

    const oaiBody = geminiToOpenAI(geminiReq);
    const bodyJson = JSON.stringify(oaiBody);
    log(`${m[2]} model=${m[1]} messages=${oaiBody.messages.length} bytes=${Buffer.byteLength(bodyJson)}`);

    try {
      if (m[2] === 'streamGenerateContent') {
        const oaiBodyStream = truncateBody(geminiToOpenAI(geminiReq, true));
        const bodyJsonStream = JSON.stringify(oaiBodyStream);
        const upstreamRes = await requestUpstream(bodyJsonStream, { stream: true });
        if (upstreamRes.statusCode !== 200) {
          let data = '';
          for await (const c of upstreamRes) data += c;
          log(`UPSTREAM ERROR ${upstreamRes.statusCode}: ${data.slice(0, 500)}`);
          sendJson(res, 502, { error: { code: 502, message: `Upstream error: ${data.slice(0, 500)}` } });
          return;
        }
        res.writeHead(200, {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        });
        const contentType = upstreamRes.headers['content-type'] || '';
        // 上游可能返回 SSE 分块（text/event-stream），也可能忽略 stream 参数返回完整 JSON。
        if (contentType.includes('text/event-stream')) {
          let buffer = '';
          const toolCallAccum = {};  // index -> {id, name, arguments}
          const textBuf = [];        // content 文本缓冲，结束时检测内联函数调用
          let finalFinishReason = null;
          upstreamRes.on('data', (chunk) => {
            buffer += chunk.toString();
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            for (const line of lines) {
              const t = line.trim();
              if (!t.startsWith('data:')) continue;
              const payload = t.slice(5).trim();
              if (payload === '[DONE]') continue;
              let oai;
              try { oai = JSON.parse(payload); } catch { continue; }
              for (const ch of oai.choices || []) {
                const d = ch.delta || {};
                // 累积 tool_calls（分块到达，结束时统一发送）
                if (d.tool_calls?.length) {
                  for (const tc of d.tool_calls) {
                    const idx = tc.index ?? 0;
                    const prev = toolCallAccum[idx] || { id: '', name: '', arguments: '' };
                    toolCallAccum[idx] = {
                      id: tc.id || prev.id,
                      name: tc.function?.name || prev.name,
                      arguments: prev.arguments + (tc.function?.arguments || ''),
                    };
                  }
                }
                // 思考内容实时转发
                const reasoning = d.reasoning_content || d.reasoning;
                if (reasoning) {
                  sendSse(res, { candidates: [{ content: { role: 'model', parts: [{ thought: true, text: reasoning }] }, finishReason: null, index: 0 }] });
                }
                // 文本内容：积累到缓冲区，流结束时检测是否内联函数调用
                if (d.content) {
                  textBuf.push(d.content);
                }
                if (ch.finish_reason) finalFinishReason = ch.finish_reason;
                // 转发 usage（最后一个 chunk 携带）
                if (oai.usage) {
                  sendSse(res, {
                    candidates: [],
                    usageMetadata: {
                      promptTokenCount: oai.usage.prompt_tokens ?? 0,
                      candidatesTokenCount: oai.usage.completion_tokens ?? 0,
                      totalTokenCount: oai.usage.total_tokens ?? 0,
                    },
                  });
                }
              }
            }
          });
          upstreamRes.on('end', () => {
            const finishMap = { stop: 'STOP', length: 'MAX_TOKENS', tool_calls: 'STOP' };
            // 检查缓冲的文本是否包含内联函数调用（部分 OpenAI 兼容后端把工具调用放 content 里）
            const fullText = textBuf.join('');
            const inlineParts = inlineCallsToParts(fullText);
            if (inlineParts) {
              // 有内联调用：发送 functionCall parts，不发送文本
              // 同时也发送已有的结构化 tool_calls（如果有的话）
              const allParts = [...inlineParts];
              // 已有的结构化 tool_calls（从 toolCallAccum）
              for (const idx of Object.keys(toolCallAccum)) {
                const tc = toolCallAccum[idx];
                let args = {};
                try { args = JSON.parse(tc.arguments || '{}'); } catch { args = {}; }
                args = adaptToolArgs(tc.name, args);
                allParts.push({ functionCall: { name: tc.name, args } });
              }
              sendSse(res, {
                candidates: [{ content: { role: 'model', parts: allParts }, finishReason: 'STOP', index: 0 }],
              });
            } else if (Object.keys(toolCallAccum).length) {
              // 有结构化工具调用
              for (const idx of Object.keys(toolCallAccum)) {
                const tc = toolCallAccum[idx];
                let args = {};
                try { args = JSON.parse(tc.arguments || '{}'); } catch { args = {}; }
                args = adaptToolArgs(tc.name, args);
                sendSse(res, {
                  candidates: [{
                    content: { role: 'model', parts: [{ functionCall: { name: tc.name, args } }] },
                    finishReason: 'STOP',
                    index: Number(idx),
                  }],
                });
              }
            } else if (textBuf.length) {
              // 纯文本：刷新缓冲
              for (const text of textBuf) {
                sendSse(res, { candidates: [{ content: { role: 'model', parts: [{ text }] }, finishReason: null, index: 0 }] });
              }
              const fr = finishMap[finalFinishReason] || 'STOP';
              sendSse(res, { candidates: [{ content: { role: 'model', parts: [] }, finishReason: fr, index: 0 }] });
            } else {
              const fr = finishMap[finalFinishReason] || 'STOP';
              sendSse(res, { candidates: [{ content: { role: 'model', parts: [] }, finishReason: fr, index: 0 }] });
            }
            res.end();
          });
        } else {
          // 完整 JSON 响应：把整个响应作为单个 SSE chunk 发出（再做一次转发）
          let data = '';
          upstreamRes.on('data', (c) => (data += c));
          upstreamRes.on('end', () => {
            try {
              const oai = JSON.parse(data);
              // 如果上游返回了带 choices 的完整响应，转成单个 Gemini chunk
              if (oai.choices && oai.choices.length) {
                const full = openAIToGemini(oai);
                const text = (full.candidates[0]?.content?.parts || [])
                  .filter((p) => p.text)
                  .map((p) => p.text)
                  .join('');
                const thought = (full.candidates[0]?.content?.parts || [])
                  .filter((p) => p.thought)
                  .map((p) => p.text)
                  .join('');
                if (text) sendSse(res, { candidates: [{ content: { role: 'model', parts: [{ text }] }, finishReason: null, index: 0 }] });
                if (thought) sendSse(res, { candidates: [{ content: { role: 'model', parts: [{ thought: true, text: thought }] }, finishReason: null, index: 0 }] });
                if (full.usageMetadata) {
                  sendSse(res, { candidates: [], usageMetadata: full.usageMetadata });
                }
                sendSse(res, { candidates: [{ content: { role: 'model', parts: [] }, finishReason: 'STOP', index: 0 }] });
              }
            } catch (e) {
              log('FULL JSON PARSE ERROR', e.message);
            }
            res.end();
          });
        }
        upstreamRes.on('error', (e) => {
          log('UPSTREAM STREAM ERROR', e.message);
          res.end();
        });
      } else {
        const truncatedBody = truncateBody(oaiBody);
        const upstreamRes = await requestUpstream(JSON.stringify(truncatedBody));
        if (upstreamRes.status !== 200) {
          log(`UPSTREAM ERROR ${upstreamRes.status}: ${upstreamRes.data.slice(0, 500)}`);
          sendJson(res, 502, {
            error: {
              code: 502,
              message: `Upstream error (${upstreamRes.status}): ${upstreamRes.data.slice(0, 500)}`,
            },
          });
          return;
        }
        let oai;
        try {
          oai = JSON.parse(upstreamRes.data);
        } catch {
          sendJson(res, 502, { error: { code: 502, message: 'Bad upstream JSON' } });
          return;
        }
        sendJson(res, 200, openAIToGemini(oai));
      }
    } catch (e) {
      log('PROXY ERROR', e.message);
      sendJson(res, 500, { error: { code: 500, message: 'Internal proxy error' } });
    }
    return;
  }

  // 其他路径
  sendJson(res, 404, { error: { code: 5, message: `NOT_FOUND: ${path}` } });
});

server.listen(PORT, HOST, () => {
  log(`Gemini->OpenAI proxy listening on http://${HOST}:${PORT}`);
  log(`Upstream: ${UPSTREAM_URL}  Model: ${MODEL}`);
});
