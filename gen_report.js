/* 智备工作台 项目报告 DOCX 生成脚本 */
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
        BorderStyle, WidthType, Table, TableRow, TableCell, ShadingType,
        Header, Footer, PageNumber, LevelFormat } = require('docx');

const OUT = path.join(__dirname, '智备工作台_项目报告.docx');

const CJK = { ascii: 'Microsoft YaHei', hAnsi: 'Microsoft YaHei', eastAsia: 'Microsoft YaHei' };

function T(text, opts={}) {
  return new TextRun({ text, font: CJK, ...opts });
}
function H1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 400, after: 200 }, children: [T(text, { bold: true, size: 36 })] }); }
function H2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 140 }, children: [T(text, { bold: true, size: 28 })] }); }
function H3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 200, after: 100 }, children: [T(text, { bold: true, size: 24 })] }); }
function P(text, opts={}) { return new Paragraph({ spacing: { before: 60, after: 60, line: 360 }, children: [T(text, { size: 22, ...opts })] }); }
function BUL(text) {
  return new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { before: 30, after: 30, line: 340 }, children: [T(text, { size: 22 })] });
}
function NUM(text) {
  return new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { before: 30, after: 30, line: 340 }, children: [T(text, { size: 22 })] });
}
function CODE(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    shading: { type: ShadingType.CLEAR, fill: 'F4F4F4' },
    border: { top:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'}, bottom:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'}, left:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'}, right:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'} },
    indent: { left: 360 },
    children: [new TextRun({ text, font: { ascii:'Consolas', hAnsi:'Consolas', eastAsia:'Microsoft YaHei' }, size: 18 })]
  });
}
function TABLE(headers, rows) {
  const colW = Math.floor(9000 / headers.length);
  const hRow = new TableRow({ cantSplit: true, children: headers.map(h => new TableCell({
    width: { size: colW, type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: 'E8F1EC' },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [T(h, { bold: true, size: 20 })] })]
  })) });
  const bodyRows = rows.map(r => new TableRow({ cantSplit: true, children: r.map(c => new TableCell({
    width: { size: colW, type: WidthType.DXA },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [T(c, { size: 20 })] })]
  })) }));
  const bd = { style: BorderStyle.SINGLE, size: 1, color: 'D6D6D6' };
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    columnWidths: headers.map(() => colW),
    rows: [hRow, ...bodyRows],
    borders: { top:bd, bottom:bd, left:bd, right:bd, insideHorizontal:bd, insideVertical:bd }
  });
}

// ====================== 封面 ======================
const cover = [
  new Paragraph({ spacing: { before: 2000 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [T('智备工作台', { bold: true, size: 72, color: '0E4C42' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120 }, children: [T('Zhi Bei Workbench', { size: 24, color: 'A88B2A' })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 80 }, children: [T('—— 教师智能备课辅助平台 ——', { size: 22, color: '6E7E76' })] }),
  new Paragraph({ spacing: { before: 600 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [T('项目完整报告', { bold: true, size: 28 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 60 }, children: [T('含前端工作台  后端服务  智能体架构  知识库系统', { size: 20, color: '6E7E76' })] }),
  new Paragraph({ spacing: { before: 1000 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [T('2026 年 11 月', { size: 20, color: '95A199' })] }),
];

// ====================== 1. 项目概览 ======================
const s1 = [
  new Paragraph({ children: [new TextRun({ text: '', break: 1 })] }),
  H1('1  项目概览'),
  P('智备工作台（Zhi Bei Workbench）是一个面向中小学教师的智能备课辅助平台。平台围绕教师备课全流程提供一站式支持：从知识库投喂、智能检索，到教学计划、教案、PPT、作业试卷的自动生成，再到文件导出与历史管理，全部在一个现代化的单页 Web 应用中完成。'),
  H2('1.1 项目定位'),
  BUL('服务对象：中小学及培训机构教师'),
  BUL('核心价值：让备课从素材拼凑变成有章法的教学设计'),
  BUL('技术路线：前端 SPA + Flask 后端 + LangGraph 智能体 + Coze 知识库'),
  H2('1.2 项目结构'),
  TABLE(['模块', '路径', '技术栈', '职责'], [
    ['前端工作台', 'workbench/index.html + login.html', '原生 JS + Tailwind CDN', '单页 SPA，工作台主界面与登录页'],
    ['后端服务', 'workbench/server.py', 'Flask + Python 3', '业务 API、鉴权、文件导出、数据持久化'],
    ['数据层', 'workbench/data/', 'JSON 文件存储', 'users.json  history.json  library.json'],
    ['智能体 Agent', 'projects/', 'LangGraph + FastAPI + Coze SDK', '备课/组卷/知识库管理核心 Agent'],
    ['工具层', 'projects/src/tools/', 'LangChain Tools', '知识检索、文件识别、文档生成'],
    ['模型配置', 'projects/config/', 'agent_llm_config.json', '系统 Prompt + LLM 参数 + 工具定义'],
  ]),
  H2('1.3 技术栈总览'),
  TABLE(['层级', '技术', '版本/说明'], [
    ['前端', '原生 JavaScript + Tailwind CSS CDN', '无构建，零依赖部署'],
    ['前端设计', '纸美学设计系统', 'Noto Serif SC + IBM Plex Mono 字体'],
    ['Web 后端', 'Flask', 'Python 3，HTTP API + Session 鉴权'],
    ['PPT 生成', 'python-pptx', '衬线/无衬线字体配对 + 字距体系'],
    ['DOCX 生成', 'python-docx', '教案/计划/试卷格式化导出'],
    ['智能体框架', 'LangGraph', 'StateGraph + create_agent'],
    ['Agent 服务', 'FastAPI + Uvicorn', 'Coze stream_run 协议'],
    ['知识库', 'Coze Knowledge API', '多路召回检索 + 文档投喂'],
    ['模型', '豆包 Doubao Seed', 'thinking=enabled, reasoning_effort=medium'],
    ['ORM', 'SQLAlchemy 2.0', 'Agent 侧 checkpoint + 异步任务存储'],
  ]),
];

// ====================== 2. 工作台前端 ======================
const s2 = [
  H1('2  工作台前端（SPA）'),
  H2('2.1 设计系统：纸美学'),
  P('工作台与登录页共享统一的「纸美学」设计语言，核心 token 在 login.html 与 index.html 中以 :root CSS 变量定义：'),
  TABLE(['Token', '色值', '用途'], [
    ['--forest', '#0E4C42', '主品牌色（按钮、重点标题、logo 方块）'],
    ['--gold', '#D4AF37', '强调色（装饰线、徽章、字眉）'],
    ['--gold-deep', '#A88B2A', '哑光金（小号字眉、标签）'],
    ['--paper', '#F4EFE3', '页面底色（仿米纸）'],
    ['--clay', '#C2492A', '错误警示色'],
    ['--ink', '#1A2A24', '正文墨色'],
    ['--line', '#E4DAC7', '边框分割线'],
    ['--serif', 'Noto Serif SC', '标题/品牌区衬线字体'],
    ['--sans', 'PingFang SC', '正文无衬线字体'],
    ['--mono', 'IBM Plex Mono', '字眉/标签/分割线等小号文字'],
  ]),
  H2('2.2 核心页面'),
  H3('登录页 login.html'),
  BUL('左右分栏布局：左侧深绿品牌区（1.05fr）+ 右侧米纸表单区（1fr）'),
  BUL('接缝装饰：贯穿全高的金色细线 + 中央光晕圆点，视觉连通两栏'),
  BUL('明金 #D4AF37 logo 方块 + 深绿「智」字 — 印章质感，对比度充足'),
  BUL('字眉层（eyebrow）Sign In + 标题「欢迎回来」+ 副标题，三级文字层次'),
  BUL('输入框三级状态：默认/hover(边框加深)/focus(墨绿光晕)/error(朱砂光晕)'),
  BUL('测试账号卡片：hover 时金色流光从左扫到右，teacher01 金色头像'),
  BUL('响应式：<900px 自动切换单列布局'),
  BUL('无障碍：prefers-reduced-motion 用户自动关闭所有动画'),
  H3('工作台 index.html'),
  BUL('顶栏：Logo + 三态 Tab（备课/组卷/资料库）+ 新建按钮 + 用户胶囊'),
  BUL('备课视图：主题/学段/课时配置 → 生成 → PPT 幻灯片预览 + 教案 Markdown → 组装导出'),
  BUL('组卷视图：章节/难度/题量 → 生成试卷 + 双向细目表 → DOCX 导出'),
  BUL('资料库视图：上传（文件粘贴）→ 批量投喂 → 已投喂列表（owner 隔离）'),
  BUL('历史视图：列表 + 详情 + 删除；恢复后 regenerate 可追加并持久化产物'),
  H2('2.3 交互状态与反馈'),
  TABLE(['操作', '反馈方式'], [
    ['表单加载中', '按钮禁用 + spinner + loading 类'],
    ['API 错误', 'form-error 卡片 + shake 动画 + 输入框抖动'],
    ['401 未授权', '全局 fetch 拦截器捕获 → 自动跳转 /login.html'],
    ['历史恢复后再次生成', 'state.historyId 绑定 → 后端 _history_update 持久化产物'],
    ['导出 PPT/DOCX', 'POST 后端接口 → RFC 5987 文件名编码 → 浏览器下载'],
  ]),
];

// ====================== 3. 后端服务 ======================
const s3 = [
  H1('3  后端服务（Flask）'),
  H2('3.1 用户与鉴权'),
  P('基于 Flask session 的 Cookie 会话，三表分离（users.json · history.json · library.json）。3 个测试账号在首次启动时自动初始化。'),
  TABLE(['账号', '密码', '显示名', '数据归属'], [
    ['teacher01', 'teacher01', '张老师', '全部现有历史 + 资料库'],
    ['teacher02', 'teacher02', '李老师', '全新空白账号'],
    ['teacher03', 'teacher03', '王老师', '全新空白账号'],
  ]),
  BUL('@_login_required 装饰器保护 12 个业务 API'),
  BUL('公开 API：/api/health · /api/login · /api/logout · /api/me · /api/test-accounts'),
  BUL('数据隔离：_lib_owner() 返回当前 user_id，history 按 owner 过滤'),
  H2('3.2 API 清单'),
  TABLE(['API', '方法', '鉴权', '职责'], [
    ['/api/login', 'POST', '公开', '账号密码登录，写 session'],
    ['/api/logout', 'POST', '公开', '清 session'],
    ['/api/me', 'GET', '公开', '返回当前用户（未登录 401）'],
    ['/api/test-accounts', 'GET', '公开', '测试账号列表（不含密码）'],
    ['/api/generate', 'POST', '已鉴', '流式调用 Agent 生成备课'],
    ['/api/regenerate', 'POST', '已鉴', '基于历史 record 再次生成，回写产物'],
    ['/api/assemble', 'POST', '已鉴', '组装教案 Markdown + 导出'],
    ['/api/paper/replace', 'POST', '已鉴', '试卷占位符替换'],
    ['/api/history', 'GET', '已鉴', '历史列表（按 owner 过滤）'],
    ['/api/history/<hid>', 'GET', '已鉴', '历史详情'],
    ['/api/library', 'GET', '已鉴', '资料库列表（按 owner 过滤）'],
    ['/api/library/upload', 'POST', '已鉴', '上传纯文本资料'],
    ['/api/library/upload-file', 'POST', '已鉴', '上传文件（粘贴 Clipboard）'],
    ['/api/export/pptx', 'POST', '已鉴', 'python-pptx 生成 PPT'],
    ['/api/export/docx', 'POST', '已鉴', 'python-docx 生成教案 DOCX'],
    ['/api/export/paper', 'POST', '已鉴', '试卷 DOCX（双向细目表）'],
  ]),
  H2('3.3 PPT 生成设计规范'),
  P('python-pptx 生成器参考用户上传的教学 PPT 模板，保留工作台品牌配色，完整实现品牌化 PPT 输出：'),
  TABLE(['元素', '设计决策'], [
    ['字体配对', 'Noto Serif SC 衬线（封面大标题、页面标题）+ 微软雅黑（正文）'],
    ['字距', '按字号自适应：42pt 2.5pt · 32pt 1.5pt · 17pt 1pt'],
    ['封面', '深绿底 + 右上浅绿三角 + 96pt 章节号 + 主副标题 + 右下智备标签'],
    ['目录页', '窄左深绿条 + 大字距「目 录」衬线 + 金色装饰线 + 两栏编号'],
    ['正文页', '衬线主标题 + 左侧金色竖条 + 右上章节号 + 青圆点项目符号 + 配图建议卡'],
    ['结束页', '深绿全屏 + 金色横线 + 54pt 大字距「谢 谢 观 看」+ Thank You'],
    ['颜色', 'forest #0E4C42 · gold #C9A961 · accent #1B8060 · light #E8F3EE'],
    ['尺寸', '13.33 × 7.5 英寸（16:9 宽屏）'],
  ]),
];

// ====================== 4. 智能体架构 ======================
const s4 = [
  H1('4  智能体架构（Teacher Agent）'),
  H2('4.1 Agent 框架'),
  P('Agent 采用 LangGraph 的 create_agent 模式构建，状态机 + Checkpointer 支持多轮对话记忆。通过 FastAPI 暴露 HTTP/SSE 接口，与前端工作台解耦部署。'),
  H2('4.2 工具注册'),
  P('Agent 注册 7 个 LangChain Tool，覆盖备课全流程：'),
  TABLE(['工具', '类型', '职责'], [
    ['recognize_document', '输入解析', 'PDF/Word/PPT/Excel/TXT/图片 OCR + 文档类型判断'],
    ['retrieve_knowledge_context', '知识检索', '多路召回（自动扩词 + 衍生查询 + 宽泛兜底 + 合并去重排序）'],
    ['search_knowledge', '知识检索', '关键词精准检索'],
    ['add_knowledge_document', '知识投喂', '单份文本/链接写入知识库'],
    ['add_knowledge_documents_batch', '知识投喂', '批量投喂（上限 50 份）'],
    ['export_teaching_document', '文档生成', 'DOCX / PDF 导出'],
    ['create_teaching_ppt', '文档生成', 'PPTX 生成'],
  ]),
  H2('4.3 System Prompt 设计要点'),
  BUL('知识检索为强制前置步骤：任何备课/组卷/课标查询第一步必须调用 retrieve_knowledge_context'),
  BUL('严格反幻觉：明确禁止编造课标条目、版本号、试题；不确定时返回「知识库暂未检索到」'),
  BUL('输出约束：正文不得含 emoji/表情/网络口语，直接返回结构化 Markdown'),
  BUL('文件识别边界：仅本次会话有效，扫描件模糊时返回 code=410'),
  H2('4.4 模型配置'),
  TABLE(['参数', '值'], [
    ['模型', 'doubao-seed-2-1-turbo-260628'],
    ['温度', '0.7'],
    ['thinking_type', 'enabled'],
    ['reasoning_effort', 'medium'],
    ['max_tokens', '4096（max_completion 10000）'],
    ['超时', '600 秒'],
  ]),
  H2('4.5 HTTP 接口'),
  TABLE(['接口', '方法', '职责'], [
    ['/run', 'POST', '同步执行 Agent，超时 15 分钟'],
    ['/stream_run', 'POST', 'SSE 流式执行（工作台前端使用）'],
    ['/async_run', 'POST', '异步任务提交'],
    ['/cancel/<run_id>', 'POST', '取消执行'],
    ['/health', 'GET', '健康检查'],
  ]),
  H2('4.6 依赖清单'),
  TABLE(['包', '版本', '用途'], [
    ['langchain + langgraph', '1.0.3 + 1.0.2', 'Agent 状态图与工具调用'],
    ['langgraph-checkpoint', '3.0.0', '对话记忆持久化'],
    ['fastapi + uvicorn', '0.121+ / 0.38+', 'Agent HTTP 服务'],
    ['coze-coding-dev-sdk', '0.5.25', '知识库/文档生成客户端'],
    ['coze-coding-utils', '0.2.8+', '运行时上下文/日志/流式辅助'],
    ['python-pptx', '1.0+', 'PPT 生成'],
    ['pymupdf + openpyxl', '6.4+ / 3.1+', 'PDF/Excel 解析'],
    ['SQLAlchemy', '2.0+', 'Checkpointer + AsyncTask 存储'],
  ]),
];

// ====================== 5. 知识库系统 ======================
const s5 = [
  H1('5  知识库系统'),
  H2('5.1 架构'),
  P('知识库基于 Coze Knowledge API（数据集 coze_doc_knowledge），支持多路召回检索 + 文档投喂。工作台侧还有独立的 BM25 关键词检索作为 Agent 不可用时的 fallback。'),
  H2('5.2 多路召回检索策略'),
  NUM('自动扩词：从用户问题中识别学科/学段/资料类型关键词'),
  NUM('衍生查询：追加 <学科> 课程标准、<学科> 教材、<学科> 真题 等变体'),
  NUM('宽泛兜底：无论命中与否，额外追加「课程标准 教学要求」和「真题 试卷 题目」'),
  NUM('合并去重 + 相关度排序：所有 chunk 按 score 降序取 top_k'),
  H2('5.3 投喂策略'),
  TABLE(['方式', '工具', '适用场景'], [
    ['单份文本/链接', 'add_knowledge_document', '一份讲义/教案/链接'],
    ['批量投喂', 'add_knowledge_documents_batch', '一次多份资料（上限 50 份）'],
    ['文件 URL 自动解析', 'KnowledgeClient + FetchClient', 'PDF/Word/PPT/网页自动解析正文后写入'],
  ]),
  H2('5.4 文件识别与 OCR'),
  TABLE(['能力', '实现方式'], [
    ['PDF 文本层提取', 'pymupdf (fitz) get_text()'],
    ['扫描版 PDF OCR', '渲染 300dpi + RapidOCR（前 20 页兜底）'],
    ['Word/PPT/Excel', 'python-docx / python-pptx / openpyxl'],
    ['图片试题 OCR', 'RapidOCR onnxruntime'],
    ['文档类型判断', '文件名 + 正文关键词打分（课标/教材/试卷/习题/教案）'],
  ]),
];

// ====================== 6. 数据结构 ======================
const s6 = [
  H1('6  数据存储与目录结构'),
  H2('6.1 工作台侧'),
  CODE('workbench/\n  server.py            # Flask 后端\n  index.html           # 工作台 SPA\n  login.html           # 登录页\n  config.py            # 环境配置\n  data/\n    users.json         # 3 个测试账号\n    history.json       # 历史备课/组卷（最多 60 条，按 owner 隔离）\n    library.json       # 资料库（owner + chunks）'),
  H2('6.2 Agent 侧（projects/）'),
  CODE('projects/\n  pyproject.toml       # uv 依赖声明\n  config/\n    agent_llm_config.json   # System Prompt + LLM 参数\n  src/\n    main.py            # FastAPI Server\n    agents/agent.py    # create_agent（7 个工具）\n    tools/\n      knowledge_tool.py\n      document_tool.py\n      file_recognize_tool.py'),
];

// ====================== 7. 测试账号使用指南 ======================
const s7 = [
  H1('7  测试账号使用指南'),
  H2('7.1 账号列表'),
  TABLE(['账号', '密码', '显示名', '数据归属'], [
    ['teacher01', 'teacher01', '张老师', '已有 1 条历史备课 + 6 份资料库'],
    ['teacher02', 'teacher02', '李老师', '全新空白账号'],
    ['teacher03', 'teacher03', '王老师', '全新空白账号'],
  ]),
  H2('7.2 一键登录'),
  BUL('打开 http://127.0.0.1:8000'),
  BUL('登录页底部「测试账号 · 一键登录」区域点击任意卡片即可自动填充并登录'),
  BUL('teacher01 金色头像 + 深色名片，已预置完整数据供演示'),
  BUL('teacher02/03 灰色头像，空白账号用于隔离验证'),
  H2('7.3 数据隔离验证步骤'),
  NUM('teacher01 登录 → 看得到 history 和 library'),
  NUM('teacher02 登录 → history=0 / library=0'),
  NUM('teacher03 登录 → history=0 / library=0'),
  NUM('三个账号 session 独立，同一后端但数据完全隔离'),
];

// ====================== 8. 启动与部署 ======================
const s8 = [
  H1('8  启动与部署'),
  H2('8.1 工作台'),
  CODE('# 启动 Flask 后端\ncd workbench\npython server.py\n# http://127.0.0.1:8000\n# data/users.json 自动初始化 3 个测试账号'),
  H2('8.2 Agent（projects/）'),
  CODE('# 安装 + 启动\nuv sync\nbash scripts/http_run.sh -m http -p 5000\n\n# 本地单次运行\nbash scripts/local_run.sh -m flow -i "你好"'),
  H2('8.3 完整工作流'),
  NUM('前端 POST /api/generate → 后端调用 Agent /stream_run（SSE 流式）'),
  NUM('Agent retrieve_knowledge_context 多路召回 → LLM 备课生成 → 返回 Markdown 结构化内容'),
  NUM('前端实时渲染预览 → 用户确认 → 后端 python-pptx / python-docx 生成文件'),
  NUM('生成文件以 RFC 5987 编码返回浏览器下载（裸 filename 仅 ASCII + filename*=UTF-8 中文 URL 编码）'),
];

// ====================== 9. 已解决问题 ======================
const s9 = [
  H1('9  已解决问题清单'),
  TABLE(['问题', '根因', '修复'], [
    ['PPT 中文字体丢失', '只设 font.name 没设 <a:ea> 东亚字体 XML', '新增 _ea_font() 统一处理'],
    ['latin-1 UnicodeEncodeError', 'Flask send_file + 裸中文 filename', '裸 filename 仅 ASCII + filename*=UTF-8 RFC 5987'],
    ['历史备课不保留新增产物', 'regenerate 没回写 history payload', '前端 historyId + 后端 _history_update'],
    ['装饰器顺序导致鉴权失效', '@_login_required 写在 Flask 路由装饰器上面', 'Flask 路由装饰器在下，自定义鉴权装饰器在上'],
    ['登录页 logo 智字看不清', '哑光暗金 + 深绿字对比度为零', '改用明金 #D4AF37 底 + 深绿字'],
    ['登录页与工作台风格不统一', '无网格纹理、配色 token 不同、字体独立', '统一纸美学 token + bg-grid 纹理 + 统一字体'],
  ]),
];

// ====================== 组装 ======================
const sections = [...cover, ...s1, ...s2, ...s3, ...s4, ...s5, ...s6, ...s7, ...s8, ...s9];

const doc = new Document({
  styles: {
    default: { document: { run: { font: CJK, size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: CJK, color: '0E4C42' },
        paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0, keepNext: false, keepLines: false } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: CJK, color: '14695B' },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 1, keepNext: false, keepLines: false } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: CJK, color: 'A88B2A' },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2, keepNext: false, keepLines: false } },
    ]
  },
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } }
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [T('智备工作台 · 项目报告', { size: 16, color: '95A199' })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
      T('第 ', { size: 16, color: '95A199' }),
      new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '95A199', font: CJK }),
      T(' 页 / 共 ', { size: 16, color: '95A199' }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: '95A199', font: CJK }),
      T(' 页', { size: 16, color: '95A199' }),
    ] })] }) },
    children: sections
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  console.log(`Report generated: ${OUT} (${(buf.length/1024).toFixed(1)} KB)`);
}).catch(e => { console.error('ERROR:', e.message); process.exit(1); });
