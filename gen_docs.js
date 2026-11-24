/* 分拆版：项目总结报告 DOCX（工作台侧）+ Agent 搭建流程文档 DOCX（Agent 侧）+ HTML PPT */
const fs = require('fs');
const path = require('path');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
        BorderStyle, WidthType, Table, TableRow, TableCell, ShadingType,
        Header, Footer, PageNumber, LevelFormat } = require('docx');

const CJK = { ascii: 'Microsoft YaHei', hAnsi: 'Microsoft YaHei', eastAsia: 'Microsoft YaHei' };
const FOREST = '0E4C42', GOLD = 'A88B2A', TEXT = '1A2A24', MUTED = '95A199', HILITE = '14695B';

function T(text, opts={}) { return new TextRun({ text, font: CJK, ...opts }); }
function H1(t){ return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing:{before:400,after:200}, children:[T(t,{bold:true,size:36})] }); }
function H2(t){ return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing:{before:280,after:140}, children:[T(t,{bold:true,size:28,color:HILITE})] }); }
function H3(t){ return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing:{before:200,after:100}, children:[T(t,{bold:true,size:24,color:GOLD})] }); }
function P(t, opts={}){ return new Paragraph({ spacing:{before:60,after:60,line:360}, children:[T(t,{size:22,...opts})] }); }
function B(t){ return new Paragraph({ numbering:{reference:'b',level:0}, spacing:{before:30,after:30,line:340}, children:[T(t,{size:22})] }); }
function N(t){ return new Paragraph({ numbering:{reference:'n',level:0}, spacing:{before:30,after:30,line:340}, children:[T(t,{size:22})] }); }
function C(t){ return new Paragraph({ spacing:{before:60,after:60}, shading:{type:ShadingType.CLEAR,fill:'F4F4F4'},
  border:{ top:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'}, bottom:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'},
           left:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'}, right:{style:BorderStyle.SINGLE,size:1,color:'CCCCCC'} },
  indent:{left:360},
  children:[new TextRun({ text:t, font:{ascii:'Consolas',hAnsi:'Consolas',eastAsia:'Microsoft YaHei'}, size:18 })] }); }
function TB(headers, rows){
  const colW = Math.floor(9000/headers.length);
  const hRow = new TableRow({ cantSplit:true, children:headers.map(h => new TableCell({
    width:{size:colW,type:WidthType.DXA}, shading:{type:ShadingType.CLEAR,fill:'E8F1EC'},
    margins:{top:80,bottom:80,left:120,right:120},
    children:[new Paragraph({children:[T(h,{bold:true,size:20})]})] })) });
  const bodyRows = rows.map(r => new TableRow({ cantSplit:true, children:r.map(c => new TableCell({
    width:{size:colW,type:WidthType.DXA}, margins:{top:80,bottom:80,left:120,right:120},
    children:[new Paragraph({children:[T(c,{size:20})]})] })) }));
  const bd = { style:BorderStyle.SINGLE, size:1, color:'D6D6D6' };
  return new Table({
    width:{size:100,type:WidthType.PERCENTAGE}, columnWidths:headers.map(()=>colW),
    rows:[hRow, ...bodyRows],
    borders:{ top:bd, bottom:bd, left:bd, right:bd, insideHorizontal:bd, insideVertical:bd } });
}

const NUM_CONFIG = [
  { reference:'b', levels:[{ level:0, format:LevelFormat.BULLET, text:'\u2022', alignment:AlignmentType.LEFT, style:{paragraph:{indent:{left:720,hanging:360}}}}] },
  { reference:'n', levels:[{ level:0, format:LevelFormat.DECIMAL, text:'%1.', alignment:AlignmentType.LEFT, style:{paragraph:{indent:{left:720,hanging:360}}}}] },
];

function mkSection(children, headerTitle, headerSubtitle){
  return new Document({
    styles:{
      default:{ document:{ run:{ font:CJK, size:22 } } },
      paragraphStyles:[
        { id:'Heading1', name:'Heading 1', basedOn:'Normal', next:'Normal', quickFormat:true,
          run:{ size:36, bold:true, font:CJK, color:FOREST },
          paragraph:{ spacing:{before:400,after:200}, outlineLevel:0, keepNext:false, keepLines:false } },
        { id:'Heading2', name:'Heading 2', basedOn:'Normal', next:'Normal', quickFormat:true,
          run:{ size:28, bold:true, font:CJK, color:HILITE },
          paragraph:{ spacing:{before:280,after:140}, outlineLevel:1, keepNext:false, keepLines:false } },
        { id:'Heading3', name:'Heading 3', basedOn:'Normal', next:'Normal', quickFormat:true,
          run:{ size:24, bold:true, font:CJK, color:GOLD },
          paragraph:{ spacing:{before:200,after:100}, outlineLevel:2, keepNext:false, keepLines:false } },
      ]
    },
    numbering:{ config:NUM_CONFIG },
    sections:[{
      properties:{ page:{ size:{width:11906,height:16838}, margin:{top:1440,right:1440,bottom:1440,left:1440} } },
      headers:{ default:new Header({ children:[new Paragraph({ alignment:AlignmentType.RIGHT, children:[T(headerTitle,{size:16,color:MUTED})] })] }) },
      footers:{ default:new Footer({ children:[new Paragraph({ alignment:AlignmentType.CENTER, children:[
        T('第 ',{size:16,color:MUTED}),
        new TextRun({ children:[PageNumber.CURRENT], size:16, color:MUTED, font:CJK }),
        T(' 页 / 共 ',{size:16,color:MUTED}),
        new TextRun({ children:[PageNumber.TOTAL_PAGES], size:16, color:MUTED, font:CJK }),
        T(' 页',{size:16,color:MUTED}),
      ] })] }) },
      children:[
        new Paragraph({ spacing:{before:1200}, children:[] }),
        new Paragraph({ alignment:AlignmentType.CENTER, children:[T(headerTitle,{bold:true,size:54,color:FOREST})] }),
        new Paragraph({ alignment:AlignmentType.CENTER, spacing:{before:120}, children:[T(headerSubtitle,{size:22,color:GOLD})] }),
        new Paragraph({ alignment:AlignmentType.CENTER, spacing:{before:60}, children:[T('Zhi Bei · 智备工作台',{size:16,color:MUTED})] }),
        new Paragraph({ spacing:{before:800}, children:[] }),
        new Paragraph({ alignment:AlignmentType.CENTER, children:[T('2026 年 11 月',{size:20,color:MUTED})] }),
        new Paragraph({ children:[new TextRun({text:'', break:1})] }),
        ...children
      ]
    }]
  });
}

// ========== 文档 1：工作台项目总结 ==========
const workbench_sections = [
  H1('一、项目定位与价值'),
  P('智备工作台（Zhi Bei Workbench）是面向中小学及培训机构教师的智能备课辅助平台。核心价值是让备课从素材拼凑变成有章法的教学设计。围绕教师备课全流程提供一站式支持：从知识库投喂、智能检索，到教学计划、教案、PPT、作业试卷的自动生成，再到文件导出与历史管理，全部在一个现代化单页 Web 应用中完成。'),
  H2('技术路线'),
  B('前端 SPA：原生 JavaScript + Tailwind CSS CDN + 纸美学设计系统'),
  B('Web 后端：Flask（Python 3）+ Session 鉴权 + JSON 文件存储'),
  B('PPT/DOCX 生成：python-pptx + python-docx（品牌化输出）'),
  B('智能体：LangGraph + FastAPI + Coze Knowledge API'),
  H2('项目结构'),
  TB(['模块','路径','职责'],[
    ['前端工作台','workbench/index.html + login.html','SPA 主界面与登录页'],
    ['后端服务','workbench/server.py','API、鉴权、导出、持久化'],
    ['数据层','workbench/data/','users · history · library JSON'],
    ['Agent 服务','projects/','备课/组卷/知识库智能体'],
  ]),

  H1('二、前端工作台'),
  H2('设计系统：纸美学'),
  P('工作台与登录页共享统一的纸美学设计语言。核心 token 以 CSS 变量定义：'),
  TB(['Token','色值','用途'],[
    ['--forest','#0E4C42','主品牌色'],
    ['--gold','#D4AF37','强调色'],
    ['--gold-deep','#A88B2A','哑光金'],
    ['--paper','#F4EFE3','仿米纸底色'],
    ['--clay','#C2492A','错误警示色'],
    ['--serif','Noto Serif SC','标题字体'],
    ['--sans','PingFang SC','正文字体'],
    ['--mono','IBM Plex Mono','字眉/标签字体'],
  ]),
  H2('登录页'),
  B('左右分栏：左侧深绿品牌区（1.05fr）+ 右侧米纸表单区（1fr）'),
  B('接缝装饰：贯穿全高的金色细线 + 中央光晕圆点'),
  B('明金 logo 方块 + 深绿"智"字（印章质感）'),
  B('字眉层（eyebrow）Sign In + 三级文字层次'),
  B('输入框四态：默认/hover/focus/error，各自独立反馈'),
  B('测试账号卡片：hover 金色流光扫过，一键登录'),
  B('响应式 <900px 自动切单列；prefers-reduced-motion 关动画'),
  H2('工作台主界面'),
  B('顶栏：Logo + 三态 Tab（备课/组卷/资料库）+ 新建 + 用户胶囊'),
  B('备课视图：主题/学段/课时 → 生成 → PPT 幻灯片预览 + 教案 Markdown → 组装导出'),
  B('组卷视图：章节/难度/题量 → 试卷 + 双向细目表 → DOCX 导出'),
  B('资料库视图：粘贴/上传 → 批量投喂 → 已投喂列表（owner 隔离）'),
  B('历史视图：列表 + 详情 + 删除；恢复后 regenerate 可追加并持久化产物'),

  H1('三、后端服务'),
  H2('鉴权体系'),
  P('基于 Flask session Cookie 会话，3 个测试账号首次启动自动初始化（data/users.json）：'),
  TB(['账号','密码','显示名','数据归属'],[
    ['teacher01','teacher01','张老师','全部现有历史 + 资料库（迁移时归属）'],
    ['teacher02','teacher02','李老师','全新空白账号'],
    ['teacher03','teacher03','王老师','全新空白账号'],
  ]),
  TB(['API 类型','列表'],[
    ['公开 5 个','login · logout · me · test-accounts · health'],
    ['已鉴 12 个','generate · regenerate · assemble · paper/replace · history×2 · library×3 · export×3'],
  ]),
  B('装饰器顺序关键：@app.get/post 在下，@_login_required 在上（Python 装饰器从下往上应用）'),
  H2('API 清单（已鉴）'),
  TB(['API','方法','职责'],[
    ['/api/generate','POST','流式调用 Agent 生成备课'],
    ['/api/regenerate','POST','基于历史 record 再次生成，回写产物'],
    ['/api/assemble','POST','组装教案 Markdown + 导出'],
    ['/api/paper/replace','POST','试卷占位符替换'],
    ['/api/history','GET','历史列表（按 owner 过滤）'],
    ['/api/history/<hid>','GET','历史详情'],
    ['/api/library','GET','资料库列表（按 owner 过滤）'],
    ['/api/library/upload','POST','上传纯文本资料'],
    ['/api/library/upload-file','POST','上传文件（粘贴 Clipboard）'],
    ['/api/export/pptx','POST','python-pptx 生成 PPT'],
    ['/api/export/docx','POST','python-docx 生成教案 DOCX'],
    ['/api/export/paper','POST','试卷 DOCX（双向细目表）'],
  ]),
  H2('PPT 生成规范'),
  TB(['元素','设计决策'],[
    ['字体配对','Noto Serif SC 衬线（大标题）+ 微软雅黑（正文）'],
    ['字距','按字号自适应：42pt 2.5pt · 32pt 1.5pt · 17pt 1pt'],
    ['封面','深绿底 + 右上浅绿三角 + 96pt 章节号 + 主副标题 + 智备标签'],
    ['目录页','窄左深绿条 + 大字距"目 录"衬线 + 金色装饰线 + 两栏编号'],
    ['正文页','衬线主标题 + 左侧金色竖条 + 章节号 + 青圆点项目符号 + 配图建议卡'],
    ['结束页','深绿全屏 + 金色横线 + 大字距"谢 谢 观 看"'],
    ['尺寸','13.33 × 7.5 英寸（16:9 宽屏）'],
  ]),
  B('中文 XML 双设置：run.font.name + <a:ea>东亚字体 — python-pptx 默认只设 ASCII 字体槽'),
  B('文件下载头：裸 filename 仅 ASCII + filename*=UTF-8\u2019\u2019 中文 URL 编码（RFC 5987）'),

  H1('四、数据隔离'),
  P('工作台侧数据全部按 owner 字段隔离，owner 值为当前登录用户 ID：'),
  B('workbench/data/users.json — 账号表（3 条）'),
  B('workbench/data/history.json — 历史备课/组卷记录，每条含 owner 字段，最多 60 条'),
  B('workbench/data/library.json — 教师资料库，每份资料含 owner + chunks（RAG 用）'),
  B('跨账号验证：teacher01 有 1 条历史 + 6 份资料库，teacher02/03 均为 0，无串扰'),

  H1('五、已解决问题清单'),
  TB(['问题','根因','修复'],[
    ['PPT 中文字体丢失','只设 font.name 没设 <a:ea> 东亚字体 XML','新增 _ea_font() 统一处理'],
    ['latin-1 UnicodeEncodeError','Flask send_file + 裸中文 filename','裸 filename 仅 ASCII + filename*=UTF-8 RFC 5987'],
    ['历史备课不保留新增产物','regenerate 没回写 history payload','前端 historyId + 后端 _history_update'],
    ['装饰器顺序导致鉴权失效','@_login_required 写在 Flask 路由装饰器上面','Flask 路由装饰器在下，自定义鉴权装饰器在上'],
    ['登录页 logo "智" 字看不清','哑光暗金 + 深绿字对比度为零','改用明金 #D4AF37 底 + 深绿字'],
    ['登录页与工作台风格不统一','无网格纹理、配色 token 不同、字体独立','统一纸美学 token + bg-grid 纹理 + 统一字体'],
  ]),

  H1('六、启动与部署'),
  C('# 启动工作台后端\ncd workbench\npython server.py\n# http://127.0.0.1:8000\n# 首次启动自动生成 3 个测试账号'),
  P('重置账号数据：删除 workbench/data 下三个 JSON 文件，重启后端即可重新初始化。'),
];

// ========== 文档 2：Agent 搭建流程 ==========
const agent_sections = [
  H1('一、架构概览'),
  P('教师备课辅助智能体基于 LangGraph + FastAPI + Coze Knowledge API 搭建。核心设计：create_agent 状态机 + 多路召回检索前置工具 + 7 个 LangChain Tool 覆盖备课全流程。'),
  H2('项目结构（projects/）'),
  C('projects/\n  pyproject.toml            # uv 依赖声明\n  README.md                 # 运行入口\n  config/\n    agent_llm_config.json   # System Prompt + LLM 参数 + 工具定义\n  src/\n    main.py                 # FastAPI Server（/run /stream_run /cancel /async_run）\n    agents/\n      agent.py              # create_agent（注册 7 个工具）\n    tools/\n      knowledge_tool.py     # 多路召回检索 + 投喂\n      document_tool.py      # DOCX/PDF/PPT 生成\n      file_recognize_tool.py# PDF/Word/PPT/Excel/图片 OCR\n    storage/\n      database/              # SQLAlchemy Checkpointer\n      memory/                # MemorySaver'),

  H1('二、依赖安装'),
  H2('方式 A：uv（推荐）'),
  C('# 自动安装 .venv 并装依赖\nuv sync\n\n# 带 lockfile 严格模式\nuv sync --frozen\n\n# Devbox 环境自动执行\n# scripts/setup.sh'),
  H2('方式 B：deploy 模式（无 .venv）'),
  C('# 将依赖导出后 pip install 到目标目录\nuv export --frozen --no-hashes --no-dev | uv pip install --no-cache --target $PIP_TARGET -r -'),
  H2('核心依赖清单'),
  TB(['包','版本','用途'],[
    ['langchain + langgraph','1.0.3 + 1.0.2','Agent 状态图与工具调用'],
    ['langgraph-checkpoint','3.0.0','对话记忆持久化（滑动窗口 40 条）'],
    ['fastapi + uvicorn','0.121+ / 0.38+','HTTP/SSE 服务'],
    ['coze-coding-dev-sdk','0.5.25','知识库/文档生成客户端'],
    ['coze-coding-utils','0.2.8+','运行时上下文/日志/流式辅助'],
    ['python-pptx','1.0+','PPT 生成'],
    ['pymupdf + openpyxl','6.4+ / 3.1+','PDF/Excel 解析'],
    ['python-docx','1.0+','Word 文档解析'],
    ['SQLAlchemy','2.0+','Checkpointer + AsyncTask 存储'],
    ['rapidocr-onnxruntime','—','扫描版 PDF / 图片试题 OCR（可选）'],
  ]),

  H1('三、Agent 注册与工具'),
  P('Agent 在 src/agents/agent.py 中通过 create_agent 构建，核心代码结构：'),
  C('# agents/agent.py 结构示意\nTOOLS = [\n  recognize_document,                  # 文件识别\n  retrieve_knowledge_context,           # 多路召回（强制前置）\n  search_knowledge,                     # 精准检索\n  add_knowledge_document,               # 单份投喂\n  add_knowledge_documents_batch,         # 批量投喂\n  export_teaching_document,             # DOCX/PDF\n  create_teaching_ppt,                  # PPTX\n]\nreturn create_agent(\n  model=ChatOpenAI(model=cfg.model, streaming=True, ...),\n  system_prompt=cfg.sp,\n  tools=TOOLS,\n  checkpointer=get_memory_saver(),\n  state_schema=AgentState,  # 滑动窗口 40 条\n)'),
  H2('7 个 LangChain Tool 详情'),
  TB(['工具','类型','职责'],[
    ['recognize_document','输入解析','PDF/Word/PPT/Excel/TXT/图片 OCR + 文档类型判断'],
    ['retrieve_knowledge_context','强制前置检索','多路召回 + 合并去重 + 相关度排序 top_k'],
    ['search_knowledge','精准检索','关键词 + 类型过滤的精准查询'],
    ['add_knowledge_document','知识投喂','单份文本/链接/URL 写入知识库'],
    ['add_knowledge_documents_batch','知识投喂','批量投喂（上限 50 份）'],
    ['export_teaching_document','文档生成','Markdown → DOCX / PDF（DocumentGenerationClient）'],
    ['create_teaching_ppt','文档生成','Markdown Slides → PPTX（DocumentGenerationClient）'],
  ]),

  H1('四、System Prompt 设计'),
  P('System Prompt 存储于 config/agent_llm_config.json，定义了四大模块：角色设定、工具定义、核心流程规范、输出约束。关键设计原则：'),
  N('知识检索强制前置：任何备课/组卷/课标查询第一步必须调用 retrieve_knowledge_context'),
  N('严格反幻觉：明确禁止编造课标条目、版本号、试题；不确定时返回「知识库暂未检索到」'),
  N('输出约束：正文不得含 emoji/表情/网络口语，直接返回结构化 Markdown'),
  N('文件识别边界：仅本次会话有效，扫描件模糊时返回 code=410 而非猜测内容'),
  N('教学专业度：输出符合课标要求、符合学段难度梯度'),
  H2('模型参数（agent_llm_config.json）'),
  TB(['参数','值'],[
    ['模型','doubao-seed-2-1-turbo-260628'],
    ['温度','0.7'],
    ['thinking_type','enabled'],
    ['reasoning_effort','medium'],
    ['max_tokens','4096（max_completion 10000）'],
    ['超时','600 秒'],
    ['知识库数据集','coze_doc_knowledge'],
  ]),

  H1('五、知识库系统'),
  H2('多路召回检索策略'),
  P('retrieve_knowledge_context 是每次回答前的强制前置工具，核心流程：'),
  N('自动扩词：从用户问题中识别学科/学段/资料类型关键词（课标/教材/真题/试卷/教案）'),
  N('衍生查询：自动追加 <学科> 课程标准、<学科> 教材、<学科> 真题、<类型> <学科> 等变体'),
  N('宽泛兜底：无论命中与否，额外追加「课程标准 教学要求」和「真题 试卷 题目」确保覆盖'),
  N('合并去重 + 相关度排序：所有查询返回的 chunk 合并去重后按 score 降序，取 top_k 返回'),
  H2('投喂策略'),
  TB(['方式','工具','适用场景'],[
    ['单份文本/链接','add_knowledge_document','一份讲义/教案/链接写入'],
    ['批量投喂','add_knowledge_documents_batch','一次多份资料（上限 50 份）'],
    ['文件 URL 自动解析','KnowledgeClient + FetchClient','PDF/Word/PPT/网页自动解析正文后写入'],
  ]),
  H2('文件识别与 OCR（file_recognize_tool.py）'),
  TB(['能力','实现方式'],[
    ['PDF 文本层提取','pymupdf (fitz) get_text()'],
    ['扫描版 PDF OCR','渲染 300dpi + RapidOCR（前 20 页兜底）'],
    ['Word','python-docx 段落 + 表格'],
    ['PPT','python-pptx 幻灯片 text_frame + 表格'],
    ['Excel','openpyxl 只读模式'],
    ['图片试题 OCR','RapidOCR onnxruntime'],
    ['文档类型判断','文件名 + 正文关键词打分（课标/教材/试卷/习题/教案）'],
  ]),
  P('识别边界：仅本次会话有效，不写入知识库、不跨会话记忆；识别失败统一返回 {"code":410,"msg":"文件识别失败"}。'),

  H1('六、HTTP 接口'),
  P('Agent 通过 FastAPI 暴露 HTTP 服务（src/main.py），Coze stream_run 协议兼容。'),
  TB(['接口','方法','职责'],[
    ['/run','POST','同步执行 Agent，超时 15 分钟'],
    ['/stream_run','POST','SSE 流式执行（工作台前端使用）'],
    ['/async_run','POST','异步任务提交（长任务）'],
    ['/cancel/<run_id>','POST','取消执行'],
    ['/node_run/<node_id>','POST','单节点独立运行'],
    ['/v1/chat/completions','POST','OpenAI Chat 兼容接口'],
    ['/health','GET','健康检查'],
  ]),
  H2('Stream Run 流程'),
  C('# 工作台后端 → Agent 流式调用\n# 前端 SSE 接收 → 实时渲染预览\nPOST /stream_run\n  body: { messages:[{role:"user", content:"..."}] }\n  response: SSE chunk stream\n  Agent 内部：\n    1. 识别 intent（备课/组卷/知识库）\n    2. 强制调用 retrieve_knowledge_context\n    3. 检索结果注入 system 上下文\n    4. LLM 流式生成 → 逐 chunk 返回\n    5. 前端实时累积 → 渲染'),

  H1('七、启动命令'),
  C('# 方式 1：HTTP 服务（工作台对接）\nbash scripts/http_run.sh -m http -p 5000\n# 等价于：python src/main.py -m http -p $PORT\n\n# 方式 2：本地单次运行\nbash scripts/local_run.sh -m flow -i "你好"\n\n# 方式 3：单节点运行\nbash scripts/local_run.sh -m node -n node_name\n\n# 打包（发布产物）\nbash scripts/pack.sh'),
  H2('环境变量'),
  TB(['变量','作用'],[
    ['COZE_WORKSPACE_PATH','Workspace 根目录（默认 /workspace/projects）'],
    ['DEPLOY_RUN_PORT','HTTP 服务端口（默认 5000）'],
    ['COZE_PROJECT_ENV','DEV 模式下自动创建 assets/ 目录'],
    ['PIP_TARGET','Deploy 模式依赖安装目标目录'],
  ]),

  H1('八、Checkpointer 与记忆'),
  P('Agent 内部滑动窗口记忆（最多 40 条消息），使用 langgraph-checkpoint 3.0.0 持久化：'),
  B('SQLAlchemy 2.0 存储 checkpoint + AsyncTask（数据库文件）'),
  B('MemorySaver 兜底（无持久化部署场景）'),
  B('每次新会话独立 checkpoint_id，不串话'),

  H1('九、已验证场景'),
  TB(['场景','验证方式'],[
    ['备课生成','工作台 → Agent /stream_run → SSE 流式 → 返回 Markdown'],
    ['知识库多路召回','测试检索 + 衍生查询合并 → 返回相关 chunk（包含课标条目）'],
    ['文件识别','recognize_document 解析上传的 Word/PDF → 返回 doc_type + content'],
    ['PPT 生成','create_teaching_ppt → 返回 DocumentGenerationClient 下载链接'],
    ['多轮对话','Session checkpoint 保留历史 → 追问上下文正确'],
    ['并发隔离','多个工作台账号登录 → Agent 各自独立会话'],
  ]),
];

// ========== 生成 ==========
async function main(){
  const r1 = await Packer.toBuffer(mkSection(workbench_sections, '智备工作台 · 项目总结报告', '教师智能备课辅助平台 — Workbench'));
  fs.writeFileSync(path.join(__dirname, '智备工作台_项目总结报告.docx'), r1);
  console.log(`✅ 工作台报告: ${r1.length} bytes`);

  const r2 = await Packer.toBuffer(mkSection(agent_sections, '教师备课辅助 Agent · 搭建流程文档', 'LangGraph + FastAPI + Coze Knowledge'));
  fs.writeFileSync(path.join(__dirname, '教师备课辅助Agent_搭建流程文档.docx'), r2);
  console.log(`✅ Agent 文档: ${r2.length} bytes`);
}
main().catch(e => { console.error(e); process.exit(1); });
