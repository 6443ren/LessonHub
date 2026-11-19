/* =========================================================
   智备 Demo · 数据层
   - 学科种子内容（演示数据，非官方课标原文）
   - 一致性计算（PRD 第 7 章唯一权威定义）
   ========================================================= */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const pick = (arr, i = 0) => arr[i % arr.length];
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nowTime = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};
const nowStamp = () => {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

const SUBJECTS = ['语文', '数学', '英语', '物理', '化学', '生物', '历史', '地理', '道德与法治', '科学', '信息技术'];
const STAGES = [
  { key: 'std', no: '01', name: '课标解析', role: '课标解析员', desc: '抽取课标条目、知识点、重难点', logs: ['检索学段 / 学科课标条目', '对齐知识点与素养要求', '标注来源，无法挂接项标「待确认」'] },
  { key: 'learner', no: '02', name: '学情分析', role: '学情分析师', desc: '前测 / 作业 → 薄弱点画像', logs: ['解析班级学情描述', '识别薄弱知识点与错误类型', '生成层次分布与教学建议'] },
  { key: 'design', no: '03', name: '教学设计', role: '教学设计员', desc: '目标 / 环节 / 时间 / 活动', logs: ['依据双锚点撰写可测量目标', '编排课堂时间线', '把薄弱点嵌入活动'] },
  { key: 'resource', no: '04', name: '资源生成', role: '资源生成员', desc: '课件大纲 / 板书 / 素材', logs: ['按环节生成课件逐页大纲', '生成板书结构', '标注每页对应环节'] },
  { key: 'assess', no: '05', name: '评价设计', role: '评价设计员', desc: '分层作业 / 评价量表', logs: ['按 A / B / C 三层命题', '为每题挂接目标与知识点', '生成评价量表维度'] },
  { key: 'review', no: '06', name: '教研审校', role: '教研审校员', desc: '一致性校验 / 溯源 / 合规', logs: ['扫描目标—活动—评价关联图', '定位断边并给出修改建议', '生成 AIGC 标注'] },
];

const TABS = [
  { key: 'std', label: '课标溯源' },
  { key: 'learner', label: '学情画像' },
  { key: 'design', label: '教学设计' },
  { key: 'slides', label: '课件板书' },
  { key: 'assess', label: '作业评价' },
  { key: 'alignment', label: '一致性仪表盘' },
];

const DEFAULT_TOPIC = { 数学: '一元二次方程的解法（配方法）', 语文: '《背影》：细节里的深情', 英语: 'Reading: The Gift of the Magi', 物理: '牛顿第一定律', 化学: '质量守恒定律', 生物: '细胞的结构与功能', 历史: '秦统一多民族封建国家的建立', 地理: '大气的受热过程', 道德与法治: '做守法的公民', 科学: '水的三态变化', 信息技术: '算法的三种基本结构' };

const DEFAULT_LEARNER = {
  数学: '本班共 40 人。前测显示：一元二次方程一般形式的识别正确率约 82%；配方法求解时，约一半学生在「等式两边同加同减」这一步出现符号错误，正确率仅 56%；判别式与根的情况对应关系混淆，正确率 61%。A 层约 12 人，B 层 20 人，C 层 8 人。课堂注意力集中时间约 20 分钟，适合讲练结合。',
  语文: '本班共 42 人。预习检测中，能准确找出文中细节描写的学生约占 68%；能说清「动作描写如何表现情感」的仅 41%；仿写练习中，多数学生只会堆叠形容词，缺少连续动作。A 层 10 人，B 层 22 人，C 层 10 人。学生喜欢朗读与讨论，但书面表达的细节意识较弱。',
  default: '本班共 40 人。前测显示：核心概念识记正确率约 78%，方法与步骤的迁移应用正确率约 58%，综合情境下的分析能力偏弱。A 层约 12 人，B 层 20 人，C 层 8 人。课堂注意力集中时间约 20 分钟，适合讲练结合、及时反馈。',
};
const learnerDefaultFor = (subject) => DEFAULT_LEARNER[subject] || DEFAULT_LEARNER.default;

const state = {
  phase: 'draft', // draft | running | review | verified | exported
  cfg: {
    stage: '初中',
    subject: '数学',
    periods: 1,
    topic: DEFAULT_TOPIC['数学'],
    learner: DEFAULT_LEARNER['数学'],
  },
  data: null,
  tab: 'std',
  stages: {},
  running: false,
  regenBusy: null,
  editedCount: 0,
  exportedAt: null,
  verifiedAt: null,
};

STAGES.forEach((s) => { state.stages[s.key] = { status: 'idle', logs: [] }; });

/* ---------------- 学科种子内容 ---------------- */

function mathPack(cfg) {
  return {
    standards: [
      { id: 'std1', code: '示例 · 数与代数 03', text: '理解一元二次方程的概念，能通过配方法、公式法、因式分解法解一元二次方程，体会转化与化归的数学思想。', source: '示例条目（演示用）', from: '义务教育数学课程标准 · 示例摘录' },
      { id: 'std2', code: '示例 · 数与代数 05', text: '能利用一元二次方程解决面积、增长率等背景的实际问题，经历「实际问题—数学模型—求解—检验」的完整过程。', source: '示例条目（演示用）', from: '义务教育数学课程标准 · 示例摘录' },
      { id: 'std3', code: '示例 · 数与代数 04', text: '会用根的判别式判断一元二次方程根的情况，理解判别式与方程解之间的对应关系。', source: '示例条目（演示用）', from: '义务教育数学课程标准 · 示例摘录' },
    ],
    knowledge: [
      { id: 'kp1', name: '一元二次方程的一般形式与系数', type: '概念', standardIds: ['std1'], note: '强调 a≠0，辨析二次项系数、一次项系数与常数项。' },
      { id: 'kp2', name: '配方法的步骤与符号处理', type: '方法', standardIds: ['std1'], note: '移项—配方—开方—求解，重点在两边同加同减。' },
      { id: 'kp3', name: '根的判别式 Δ=b²-4ac', type: '方法', standardIds: ['std3'], note: 'Δ 的符号与根的个数、是否相等的对应。' },
      { id: 'kp4', name: '列方程解实际问题', type: '应用', standardIds: ['std2'], note: '设未知数、找等量关系、检验解的合理性。' },
    ],
    learner: {
      weak: [
        { kpId: 'kp2', name: '配方法中「两边同加同减」的符号处理', evidence: '前测第 3、5 题：56% 的学生在配方步骤丢失或写错常数项', rate: '正确率 56%', suggestion: '提供「一移、二配、三解」步骤卡，配 2 道对照练习即时反馈' },
        { kpId: 'kp3', name: '判别式与根的情况的对应', evidence: '作业抽样：61% 的学生能算出 Δ，但说不出「Δ>0 有两个不等实根」的依据', rate: '正确率 61%', suggestion: '用图象交点个数建立 Δ 与根的对应，再做口头说理训练' },
      ],
      dist: { A: 12, B: 20, C: 8 },
      suggestions: [
        '讲练结合，连续讲授不超过 20 分钟，中途安排一次快问快答。',
        'A 层减少机械重复题，增加变式与说理；C 层在建模任务中提供半成品脚手架。',
        '把配方法的符号错误做成「错例对比」环节，让学生自己找错。',
      ],
    },
    objectives: [
      { id: 'o1', code: 'O1', text: '通过具体方程实例，能准确写出一般形式并指出二次项系数、一次项系数与常数项，正确率不低于 80%。', kpIds: ['kp1'], standardIds: ['std1'], alt: '能在 3 个具体实例中辨认一元二次方程，并用一般形式规范表示，正确率不低于 80%。' },
      { id: 'o2', code: 'O2', text: '能在教师示范后独立完成 2 道配方法求解，步骤完整、符号正确，达成率不低于 75%。', kpIds: ['kp2'], standardIds: ['std1'], alt: '能按「移项—配方—开方—求解」四步完成配方法求解，并自查符号，达成率不低于 75%。' },
      { id: 'o3', code: 'O3', text: '能根据判别式的值判断方程根的情况，并用一句话说明理由，正确率不低于 70%。', kpIds: ['kp3'], standardIds: ['std3'], alt: '能由 Δ 的符号推出根的个数与是否相等，并说明依据，正确率不低于 70%。' },
      { id: 'o4', code: 'O4', text: '能列一元二次方程解决一道面积类实际问题，并检验解的合理性，至少完成 1 道完整建模。', kpIds: ['kp4'], standardIds: ['std2'], alt: '能把一道面积情境转化为一元二次方程，完成求解并写出检验结论，至少 1 道。' },
    ],
    segments: [
      { id: 's1', code: 'S1', name: '情境导入', minutes: 4, activity: '以「长方形花圃面积」问题设疑：已知周长与面积，如何求边长？引导学生把问题转化为方程。', objectiveIds: [], altActivity: '用校园花圃改造的真实情境引入：给定周长与面积，倒推边长，制造认知冲突。' },
      { id: 's2', code: 'S2', name: '概念建构', minutes: 9, activity: '观察 4 个方程的共同结构，归纳一元二次方程的一般形式，辨析 a≠0 的必要性；随堂 3 题快问快答。', objectiveIds: ['o1'], altActivity: '对比一元一次方程与一元二次方程的结构差异，学生分类后共同归纳一般形式，完成 3 题系数辨识。' },
      { id: 's3', code: 'S3', name: '方法探究：配方法', minutes: 14, activity: '从 x²=9 与 (x+3)²=16 入手，示范「移项—配方—开方—求解」，针对符号易错点做对照演示；学生完成 2 道同类题。', objectiveIds: ['o2'], altActivity: '以「补全正方形」的几何直观解释配方，示范四步流程，随后学生对照步骤卡完成 2 题并互评。' },
      { id: 's4', code: 'S4', name: '分层练习', minutes: 7, activity: 'A 层完成配方填空，B 层独立解方程，C 层判断根的情况并说明理由；教师巡视，收集典型错误。', objectiveIds: ['o2', 'o3'], altActivity: '三层任务同时下发：A 层填空支架、B 层整题求解、C 层判别式说理，教师按层巡视并即时反馈。' },
      { id: 's5', code: 'S5', name: '建模应用', minutes: 5, activity: '回到导入问题，示范设未知数、列方程、求解与检验，学生补全解题过程。', objectiveIds: ['o4'], altActivity: '回到花圃情境，师生共同完成「设—列—解—验」四步，学生补写检验与作答。' },
      { id: 's6', code: 'S6', name: '课堂小结', minutes: 1, activity: '用「一般形式—配方法—判别式」三个关键词回顾，布置分层作业。', objectiveIds: ['o1', 'o2', 'o3', 'o4'], altActivity: '学生用一句话概括本课方法，教师补充知识结构图并布置分层作业。' },
    ],
    slides: [
      { id: 'sl1', title: '一块花圃引发的方程', segId: 's1', points: ['周长为 26 m，面积为 40 m²', '设宽为 x，长怎么表示？', '能把条件写成一个方程吗？'], note: '先不急着求解，让学生感受「问题 → 方程」的转化。' },
      { id: 'sl2', title: '一元二次方程的一般形式', segId: 's2', points: ['ax²+bx+c=0（a≠0）', 'a、b、c 分别叫什么？', '为什么必须 a≠0？'], note: '用反例 x²+2x=0 与 0·x²+2x=0 对比说明。' },
      { id: 'sl3', title: '三题快问快答', segId: 's2', points: ['3x²-6x=2 → 一般形式？', '各项系数分别是什么？', '哪些是一元二次方程？'], note: '点名回答，暴露学生对「移项后定系数」的误判。' },
      { id: 'sl4', title: '配方法四步流程', segId: 's3', points: ['① 移项：常数项移到右边', '② 配方：两边同加 (b/2)²', '③ 开方：注意 ± 号', '④ 求解：写出两个根'], note: '每一步配合一个手势记忆，突出「同加同减」。' },
      { id: 'sl5', title: '典型错例：少了一个常数', segId: 's3', points: ['x²+4x-5=0', '错解：(x+2)²=9 → x+2=3', '漏掉了 x₂=-5'], note: '让学生先判断对错，再说明错在哪一步。' },
      { id: 'sl6', title: '分层任务单', segId: 's4', points: ['A：配方填空（支架题）', 'B：独立完成两道方程', 'C：判别式判断并说理'], note: '三层任务同时下发，避免学生等待。' },
      { id: 'sl7', title: '回到花圃：设、列、解、验', segId: 's5', points: ['设宽 x，长 x+3', 'x(x+3)=40', 'x=5，长 8 m'], note: '强调检验：边长不能为负，取正根。' },
    ],
    board: '一元二次方程 ax² + bx + c = 0（a ≠ 0）\n\n  一般形式 → 定系数 a、b、c\n\n  配方法：移项 → 配方 → 开方 → 求解\n     x² + 4x − 5 = 0\n     (x + 2)² = 9 → x₁ = 1，x₂ = −5\n\n  判别式  Δ = b² − 4ac\n     Δ > 0  两个不等实根\n     Δ = 0  两个相等实根\n     Δ < 0  无实数根',
    assessments: [
      { id: 'a1', code: 'A1', level: 'A', stem: '把方程 3x² − 6x = 2 化为一般形式，并写出 a、b、c 的值。', answer: '3x² − 6x − 2 = 0，a = 3，b = −6，c = −2。', kpIds: ['kp1'], objectiveIds: ['o1'], altStem: '指出方程 2x² = 5x 的二次项系数、一次项系数与常数项。' },
      { id: 'a2', code: 'A2', level: 'A', stem: '用配方法解方程 x² + 4x − 5 = 0，写出配方步骤。', answer: '移项得 x² + 4x = 5；两边加 4 得 (x+2)² = 9；开方得 x+2 = ±3；所以 x₁ = 1，x₂ = −5。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: '用配方法解方程 x² − 6x + 5 = 0，并写出每一步依据。' },
      { id: 'b1', code: 'B1', level: 'B', stem: '用配方法解方程 2x² − 5x + 2 = 0。', answer: '两边除以 2 得 x² − (5/2)x + 1 = 0；配方得 (x − 5/4)² = 9/16；所以 x₁ = 2，x₂ = 1/2。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: '用配方法解方程 3x² − 6x − 1 = 0，结果保留根号。' },
      { id: 'b2', code: 'B2', level: 'B', stem: '不解方程，判断 x² − 3x + 5 = 0 的根的情况，并说明理由。', answer: 'Δ = (−3)² − 4×1×5 = −11 < 0，所以方程没有实数根。', kpIds: ['kp3'], objectiveIds: ['o3'], altStem: '判断方程 x² + 2x − 3 = 0 的根的情况，并说明判别式的值。' },
      { id: 'c1', code: 'C1', level: 'C', stem: '若关于 x 的方程 x² − 2x + m = 0 有两个相等的实数根，求 m 的值，并求出此时方程的根。', answer: 'Δ = 4 − 4m = 0，得 m = 1；此时方程为 (x−1)² = 0，所以 x₁ = x₂ = 1。', kpIds: ['kp3'], objectiveIds: ['o3'], altStem: '若方程 x² + kx + 9 = 0 有两个相等的实数根，求 k 的值并解方程。' },
    ],
    rubric: [
      { dim: '概念理解', levels: ['能说出一般形式，系数辨识有少量笔误', '能准确辨识 a、b、c，并说明 a≠0 的原因', '能举例说明 a=0 时方程退化的原因，并自主纠错'] },
      { dim: '配方法运用', levels: ['需借助步骤卡完成，符号偶有遗漏', '能独立完成配方与开方，步骤完整', '能迁移到二次项系数不为 1 的情形并自查'] },
      { dim: '建模与检验', levels: ['能列出方程，检验意识不足', '能完成设、列、解、验四步', '能自主选择建模方式并解释取根理由'] },
    ],
  };
}

function chinesePack(cfg) {
  return {
    standards: [
      { id: 'std1', code: '示例 · 阅读与鉴赏 07', text: '阅读叙事性散文，能梳理文章脉络，品味关键语句在具体语境中的表达效果。', source: '示例条目（演示用）', from: '义务教育语文课程标准 · 示例摘录' },
      { id: 'std2', code: '示例 · 表达与交流 04', text: '能抓住人物特征进行细节描写，做到具体、连贯，表达真情实感。', source: '示例条目（演示用）', from: '义务教育语文课程标准 · 示例摘录' },
      { id: 'std3', code: '示例 · 阅读与鉴赏 09', text: '能结合写作背景理解作者情感，对作品的思想感情作出自己的评价。', source: '示例条目（演示用）', from: '义务教育语文课程标准 · 示例摘录' },
    ],
    knowledge: [
      { id: 'kp1', name: '细节描写的类型与选取', type: '概念', standardIds: ['std1'], note: '外貌、动作、语言、场景等细节及其表达功能。' },
      { id: 'kp2', name: '动作细节的表达效果', type: '方法', standardIds: ['std1'], note: '关注动词的连续性与修饰语的分寸。' },
      { id: 'kp3', name: '反复与照应的结构作用', type: '方法', standardIds: ['std1'], note: '四次「背影」形成情感递进。' },
      { id: 'kp4', name: '细节仿写与真情表达', type: '应用', standardIds: ['std2'], note: '用连续动作写一个熟悉的人。' },
    ],
    learner: {
      weak: [
        { kpId: 'kp2', name: '说不清动作描写「怎么写出了情感」', evidence: '预习检测：仅 41% 的学生能从动词角度说明表达效果', rate: '正确率 41%', suggestion: '用「换词比较 + 删词比较」双栏表格，训练从词语到情感的推理' },
        { kpId: 'kp3', name: '忽略反复出现的细节与情感递进的关系', evidence: '课堂提问：多数学生只记得「买橘子」，说不清四次背影的差异', rate: '提及率 35%', suggestion: '用情感曲线图串联四次背影，标注每次的情感变化' },
      ],
      dist: { A: 10, B: 22, C: 10 },
      suggestions: [
        '先读后析：保证 8 分钟默读与批注，避免用讲解代替阅读。',
        '仿写给支架：提供「动作链 + 一个反常细节」的半成品。',
        'C 层可减少概念辨析，聚焦朗读与口头表达。',
      ],
    },
    objectives: [
      { id: 'o1', code: 'O1', text: '能准确找出文中三处「背影」细节描写，并标注其在文中的位置与作用，正确率不低于 85%。', kpIds: ['kp1'], standardIds: ['std1'], alt: '能在通读后标出三处核心细节描写，并用一句话概括各自作用，正确率不低于 85%。' },
      { id: 'o2', code: 'O2', text: '能从动词与修饰语的角度分析一处细节描写，说明其对刻画人物形象的作用，达成率不低于 70%。', kpIds: ['kp2'], standardIds: ['std1'], alt: '能通过换词、删词比较，说出动词选择对人物形象的影响，达成率不低于 70%。' },
      { id: 'o3', code: 'O3', text: '能仿写一段 150 字左右的细节描写，至少使用三个连续动作，体现人物性格。', kpIds: ['kp4'], standardIds: ['std2'], alt: '能围绕一个熟悉的人写一段细节描写，动作连贯、细节真实，不少于 150 字。' },
      { id: 'o4', code: 'O4', text: '能结合写作背景与四次「背影」的变化，说出作者情感的变化线索。', kpIds: ['kp3'], standardIds: ['std3'], alt: '能借助情感曲线图，说明作者从「不耐烦」到「自责与怀念」的变化依据。' },
    ],
    segments: [
      { id: 's1', code: 'S1', name: '情境导入', minutes: 4, activity: '播放父子车站分别的短视频片段，提问：哪一个细节最打动你？为什么？', objectiveIds: [], altActivity: '展示两张父子背影照片，请学生用一句话描述其中最能打动自己的细节。' },
      { id: 's2', code: 'S2', name: '整体感知', minutes: 8, activity: '默读全文，圈画四次「背影」，用时间轴标注每次出现的位置与情境。', objectiveIds: ['o1', 'o4'], altActivity: '带着「四次背影有何不同」的问题默读，完成时间轴批注。' },
      { id: 's3', code: 'S3', name: '细读品析', minutes: 16, activity: '聚焦「攀、缩、倾」等动词，用换词、删词比较法分析表达效果；小组汇报。', objectiveIds: ['o2', 'o4'], altActivity: '围绕「攀、缩、倾」三个动词做换词比较，小组用「删掉它，感觉有什么不同」句式汇报。' },
      { id: 's4', code: 'S4', name: '仿写迁移', minutes: 9, activity: '用三个连续动作写一个熟悉的人，要求至少一个反常细节，完成后同桌互评。', objectiveIds: ['o3'], altActivity: '以「背影」为题，用三个连续动作写一个熟悉的人，同桌按量表互评。' },
      { id: 's5', code: 'S5', name: '交流评价', minutes: 2, activity: '展示两篇仿写，依据量表点评「细节是否具体、情感是否真实」。', objectiveIds: ['o3'], altActivity: '选取两篇仿写对照量表点评，聚焦「细节是否服务于情感」。' },
      { id: 's6', code: 'S6', name: '课堂小结', minutes: 1, activity: '用「细节—动词—情感」三个关键词回顾，布置分层作业。', objectiveIds: ['o1', 'o2', 'o4'], altActivity: '学生用一句话总结「细节如何承载情感」，教师板书结构。' },
    ],
    slides: [
      { id: 'sl1', title: '哪一个细节打动了你', segId: 's1', points: ['观看车站离别片段', '用一个词描述你的感受', '作者写的是哪个细节？'], note: '不急于给结论，保留学生的第一感受。' },
      { id: 'sl2', title: '四次背影，一条时间轴', segId: 's2', points: ['第一次：惦记背影', '第二次：刻画背影', '第三次：惜别背影', '第四次：再现背影'], note: '让学生在文中标出四次出现的位置。' },
      { id: 'sl3', title: '动词里的深情：攀、缩、倾', segId: 's3', points: ['换词：攀→爬，效果一样吗？', '删词：删掉「缩」，少了什么？', '动作背后是谁的身体与心境？'], note: '用比较法，让学生自己说出表达效果。' },
      { id: 'sl4', title: '情感曲线：不耐烦 → 自责 → 怀念', segId: 's3', points: ['「我那时真是聪明过分」', '两次流泪的位置', '结尾的「背影」为何更重'], objectiveNote: '', note: '把情感变化画成曲线，帮助学生建立整体感。' },
      { id: 'sl5', title: '仿写支架：三个连续动作', segId: 's4', points: ['选一个熟悉的人', '写三个连贯动作', '加入一个反常细节', '不出现「爱」字'], note: '强调「不出现爱字」，用细节表达情感。' },
      { id: 'sl6', title: '评价量表', segId: 's5', points: ['细节具体（40%）', '动作连贯（30%）', '情感真实（30%）'], note: '同桌互评时逐项打勾，并写一条改进建议。' },
    ],
    board: '《背影》—— 细节里的深情\n\n  四次背影\n    ① 惦记背影 → ② 刻画背影\n    ③ 惜别背影 → ④ 再现背影\n\n  动词品析：攀 · 缩 · 倾\n    换词比较 / 删词比较 → 读出艰难与父爱\n\n  情感线索\n    不耐烦 → 触动 → 自责 → 怀念\n\n  写：三个连续动作 + 一个反常细节',
    assessments: [
      { id: 'a1', code: 'A1', level: 'A', stem: '文中四次写到「背影」，请按顺序写出每次出现的情境。', answer: '① 开篇惦记父亲的背影；② 车站买橘时的背影；③ 分别时目送父亲离去的背影；④ 结尾读信时再现的背影。', kpIds: ['kp1'], objectiveIds: ['o1', 'o4'], altStem: '请找出文中描写父亲买橘子的段落，并概括其主要内容。' },
      { id: 'a2', code: 'A2', level: 'A', stem: '「他用两手攀着上面，两脚再向上缩」中的「攀」「缩」能否换成「抓」「抬」？为什么？', answer: '不能。「攀」「缩」写出月台高、父亲体胖行动艰难，更能表现父亲为儿子付出的不易与深情。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: '赏析「蹒跚」「慢慢」两个词在句中的表达效果。' },
      { id: 'b1', code: 'B1', level: 'B', stem: '结合全文，说说作者对父亲的情感发生了怎样的变化，并找出两处依据。', answer: '由最初的不耐烦、觉得「聪明过分」，到被背影触动而流泪，再到自责与怀念；依据如两次流泪、「我那时真是聪明过分」等。', kpIds: ['kp3'], objectiveIds: ['o4'], altStem: '文中两次写「我流泪了」，这两次流泪的原因有何不同？' },
      { id: 'b2', code: 'B2', level: 'B', stem: '请从动词使用的角度，分析「攀」「缩」「倾」三个动作如何刻画父亲形象。', answer: '三个动词连续、笨拙而吃力，写出父亲翻越月台的不易，以动作之难反衬爱之深。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: '文中父亲的「背影」为何让作者「赶紧拭干了泪」？结合动作描写回答。' },
      { id: 'c1', code: 'C1', level: 'C', stem: '有同学认为文章开头写家庭变故与主旨无关，可以删去。你是否同意？结合文本说明理由。', answer: '不同意。家庭变故交代了背景，使父亲的处境更艰难，也让「背影」承载的父爱与责任更沉重，删去会削弱情感力量。', kpIds: ['kp3'], objectiveIds: ['o1', 'o4'], altStem: '文章结尾再次写「背影」，与开头相比多了什么意味？结合写作背景分析。' },
    ],
    rubric: [
      { dim: '细节识别', levels: ['能找到部分细节，位置标注不准', '能准确定位三处细节并概括作用', '能辨析细节的主次及其结构功能'] },
      { dim: '语言品析', levels: ['能说出感受，缺少文本依据', '能结合动词与语境说明表达效果', '能通过比较法作出有理有据的赏析'] },
      { dim: '仿写表达', levels: ['有细节但不够具体，动作不连贯', '能用三个连续动作写清一件事', '细节服务于人物性格，情感真挚自然'] },
    ],
  };
}

function genericPack(cfg) {
  const t = cfg.topic;
  return {
    standards: [
      { id: 'std1', code: '示例 · 内容要求 01', text: `理解「${t}」涉及的核心概念与基本规律，能在具体情境中作出解释。`, source: '示例条目（演示用）', from: `${cfg.stage}${cfg.subject}课程标准 · 示例摘录` },
      { id: 'std2', code: '示例 · 学业要求 02', text: `能运用「${t}」的相关方法分析并解决简单问题，经历「观察—归纳—应用」的过程。`, source: '示例条目（演示用）', from: `${cfg.stage}${cfg.subject}课程标准 · 示例摘录` },
      { id: 'std3', code: '示例 · 素养要求 03', text: '能在真实情境中迁移所学内容，形成结构化认识并作出合理判断。', source: '示例条目（演示用）', from: `${cfg.stage}${cfg.subject}课程标准 · 示例摘录` },
    ],
    knowledge: [
      { id: 'kp1', name: `${t}·核心概念`, type: '概念', standardIds: ['std1'], note: '本课最基础的概念与术语。' },
      { id: 'kp2', name: `${t}·基本方法`, type: '方法', standardIds: ['std2'], note: '可迁移的操作步骤与思维方法。' },
      { id: 'kp3', name: `${t}·迁移应用`, type: '应用', standardIds: ['std3'], note: '在新情境中调用本课内容。' },
    ],
    learner: {
      weak: [
        { kpId: 'kp2', name: `${t}·基本方法的步骤迁移`, evidence: '前测：约 58% 的学生能复述结论，但独立完成变式时步骤不完整', rate: '正确率 58%', suggestion: '把方法拆成可检查的步骤卡，配变式练习即时纠错' },
        { kpId: 'kp3', name: `${t}·新情境中的迁移`, evidence: '作业抽样：仅 46% 的学生能在陌生情境中调用本课方法', rate: '正确率 46%', suggestion: '设计一个贴近生活的情境任务，提供半成品支架' },
      ],
      dist: { A: 12, B: 20, C: 8 },
      suggestions: [
        '讲练结合，每 10 分钟安排一次小反馈，避免单向讲授。',
        '用真实情境贯穿导入与迁移，减少抽象术语的堆叠。',
        'C 层提供步骤卡与样例，A 层增加开放性问题。',
      ],
    },
    objectives: [
      { id: 'o1', code: 'O1', text: `能用自己的话说出「${t}」的核心概念，并准确举例，正确率不低于 80%。`, kpIds: ['kp1'], standardIds: ['std1'], alt: `能准确解释「${t}」的关键术语，并区分正例与反例，正确率不低于 80%。` },
      { id: 'o2', code: 'O2', text: `能按规范步骤完成 2 道「${t}」的基础任务，步骤完整，达成率不低于 75%。`, kpIds: ['kp2'], standardIds: ['std2'], alt: `能在步骤卡提示下完成 2 项「${t}」的基本操作，达成率不低于 75%。` },
      { id: 'o3', code: 'O3', text: `能在新情境中运用「${t}」的方法解决 1 个问题，并说明理由。`, kpIds: ['kp3'], standardIds: ['std3'], alt: `能把「${t}」迁移到一个陌生情境，写出解决思路与依据。` },
      { id: 'o4', code: 'O4', text: '能在小组交流中评价同伴的方案，提出至少 1 条改进建议。', kpIds: ['kp3'], standardIds: ['std3'], alt: '能依据评价量表对同伴方案作出判断，并给出具体改进建议。' },
    ],
    segments: [
      { id: 's1', code: 'S1', name: '情境导入', minutes: 4, activity: `用一个与「${t}」相关的生活现象设疑，暴露学生的前概念。`, objectiveIds: [], altActivity: `展示一个与「${t}」有关的现象，请学生先猜一猜、再说理由。` },
      { id: 's2', code: 'S2', name: '概念建构', minutes: 10, activity: `结合实例归纳「${t}」的核心概念，辨析易混点，完成 3 题快速判断。`, objectiveIds: ['o1'], altActivity: `对比正例与反例，师生共同提炼「${t}」的关键特征。` },
      { id: 's3', code: 'S3', name: '方法探究', minutes: 13, activity: `示范「${t}」的基本方法与步骤，学生跟随完成 1 道示范任务，再独立完成 2 道练习。`, objectiveIds: ['o2'], altActivity: `用步骤卡拆解「${t}」的操作流程，学生对照完成 2 项任务。` },
      { id: 's4', code: 'S4', name: '迁移应用', minutes: 10, activity: `呈现新情境任务，小组合作运用「${t}」解决问题，并说明理由。`, objectiveIds: ['o2', 'o3'], altActivity: `给出一个陌生情境，小组讨论解决路径并写出依据。` },
      { id: 's5', code: 'S5', name: '交流评价', minutes: 2, activity: '两组展示方案，其他学生依据量表提出改进建议。', objectiveIds: ['o4'], altActivity: '两组汇报，其余学生用评价量表打勾并写一条建议。' },
      { id: 's6', code: 'S6', name: '课堂小结', minutes: 1, activity: `用「${t}」的概念—方法—应用三个关键词回顾，布置分层作业。`, objectiveIds: ['o1', 'o2'], altActivity: '学生用一句话概括本课收获，教师补齐结构图。' },
    ],
    slides: [
      { id: 'sl1', title: `从一个现象说起：${t}`, segId: 's1', points: ['观察现象，写下你的猜测', '你的依据是什么？', '本课要解决什么问题'], note: '先暴露前概念，不急着纠正。' },
      { id: 'sl2', title: `核心概念：${t}`, segId: 's2', points: ['关键词一：……', '关键词二：……', '正例 / 反例辨析'], note: '用对比帮助学生抓住本质特征。' },
      { id: 'sl3', title: '方法与步骤', segId: 's3', points: ['第一步：观察与提取', '第二步：选择方法', '第三步：检验与表达'], note: '步骤卡同步下发，降低认知负荷。' },
      { id: 'sl4', title: '新情境挑战', segId: 's4', points: ['情境任务单', '小组分工与记录', '结果与理由'], note: '强调说理，而不只是答案。' },
      { id: 'sl5', title: '评价与小结', segId: 's5', points: ['评价量表三维度', '一条具体改进建议', '概念—方法—应用'], note: '互评要指向可操作的改进。' },
    ],
    board: `${t}\n\n  概念\n    关键词 ① ______\n    关键词 ② ______\n\n  方法\n    观察 → 提取 → 选择 → 检验\n\n  应用\n    新情境 → 调用方法 → 说明理由\n\n  易错点\n    □ 步骤不完整   □ 忽略条件   □ 结论无依据`,
    assessments: [
      { id: 'a1', code: 'A1', level: 'A', stem: `下列关于「${t}」的说法中，正确的一项是（ ）。`, answer: '答案：B。解析：A、C 混淆了概念边界，D 忽略了成立条件。', kpIds: ['kp1'], objectiveIds: ['o1'], altStem: `请用自己的话解释「${t}」的核心概念，并举一个例子。` },
      { id: 'a2', code: 'A2', level: 'A', stem: `按步骤完成一道「${t}」的基础任务，写出关键步骤。`, answer: '答案要点：步骤完整、术语准确、结论有依据。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: `完成「${t}」的步骤填空，并说明每一步的作用。` },
      { id: 'b1', code: 'B1', level: 'B', stem: `运用「${t}」的方法解决一个变式问题，并说明理由。`, answer: '答案要点：正确调用方法；理由需指向概念或条件。', kpIds: ['kp2'], objectiveIds: ['o2'], altStem: `给出一个变式任务，说明为什么不能直接套用原方法。` },
      { id: 'b2', code: 'B2', level: 'B', stem: `在新情境中，「${t}」是否仍然适用？说明你的判断依据。`, answer: '答案要点：判断明确；依据需结合情境条件与概念边界。', kpIds: ['kp3'], objectiveIds: ['o3'], altStem: `比较两个情境的异同，判断「${t}」的适用条件。` },
      { id: 'c1', code: 'C1', level: 'C', stem: `设计一个能体现「${t}」的实例，并说明其合理性。`, answer: '答案要点：实例真实；能对应核心概念；说明有条理。', kpIds: ['kp3'], objectiveIds: ['o3'], altStem: `对同伴的方案提出一条改进建议，并说明理由。` },
    ],
    rubric: [
      { dim: '概念理解', levels: ['能复述部分术语，举例不当', '能准确解释概念并给出正例', '能辨析边界条件并自主纠错'] },
      { dim: '方法运用', levels: ['步骤依赖提示，偶有遗漏', '能独立完成规范步骤', '能选择合适方法并解释理由'] },
      { dim: '迁移表达', levels: ['在新情境中无从下手', '能调用方法解决熟悉情境', '能迁移到陌生情境并清晰说理'] },
    ],
  };
}

/**
 * 把「模型返回的包」或「本地种子包」补齐为前端可渲染的完整数据。
 * 真实模型与演示引擎共用同一套结构，保证界面、一致性计算完全一致。
 */
function preparePackage(pack, cfg, extra = {}) {
  pack.meta = {
    stage: cfg.stage,
    subject: cfg.subject,
    periods: cfg.periods,
    topic: cfg.topic,
    learnerText: cfg.learner,
    createdAt: extra.createdAt || nowStamp(),
    dataMode: extra.dataMode || '演示模式',
    mode: extra.mode || 'demo',
    model: extra.model || '本地演示引擎',
    elapsed: extra.elapsed != null ? extra.elapsed : null,
    usage: extra.usage || null,
    cached: !!extra.cached,
  };
  pack.standards.forEach((s) => { s.edited = false; });
  pack.knowledge.forEach((k) => { k.locked = false; k.edited = false; });
  pack.objectives.forEach((o) => { o.locked = false; o.edited = false; });
  pack.segments.forEach((s) => { s.locked = false; s.edited = false; });
  pack.slides.forEach((s) => { s.locked = false; s.edited = false; });
  pack.assessments.forEach((a) => { a.locked = false; a.edited = false; });
  pack.board = { text: pack.board && pack.board.text ? pack.board.text : String(pack.board || ''), locked: false, edited: false };
  pack.learner.empty = !String(cfg.learner || '').trim();
  if (pack.learner.empty && !(pack.learner.suggestions || []).some((s) => String(s).includes('通用'))) {
    pack.learner.suggestions = ['未提供学情，以下建议基于通用教学经验，请结合班级实际情况调整。', ...pack.learner.suggestions];
  }
  // 生成溯源链条
  pack.objectives.forEach((o) => { o.trace = o.standardIds.map((id) => pack.standards.find((s) => s.id === id)).filter(Boolean); });
  return pack;
}

function buildData(cfg) {
  let pack;
  if (cfg.subject === '数学') pack = mathPack(cfg);
  else if (cfg.subject === '语文') pack = chinesePack(cfg);
  else pack = genericPack(cfg);
  return preparePackage(pack, cfg);
}

/* ---------------- 一致性计算 ---------------- */

function alignment(d) {
  const objectives = d.objectives || [];
  const segments = d.segments || [];
  const assessments = d.assessments || [];
  const issues = [];
  const objIds = new Set(objectives.map((o) => o.id));
  const segIds = new Set(segments.map((s) => s.id));

  const segByObj = {};
  const asByObj = {};
  objectives.forEach((o) => { segByObj[o.id] = []; asByObj[o.id] = []; });
  segments.forEach((s) => s.objectiveIds.forEach((id) => { if (segByObj[id]) segByObj[id].push(s.id); }));
  assessments.forEach((a) => a.objectiveIds.forEach((id) => { if (asByObj[id]) asByObj[id].push(a.id); }));

  // 悬空引用
  segments.forEach((s) => {
    s.objectiveIds.forEach((id) => {
      if (!objIds.has(id)) {
        issues.push({ severity: 'high', type: '悬空引用', tab: 'design', targetId: s.id, detail: `教学环节「${s.name}」引用了不存在的目标 ${id}。`, suggestion: '修正引用或删除失效关联。' });
      }
    });
  });
  assessments.forEach((a) => {
    a.objectiveIds.forEach((id) => {
      if (!objIds.has(id)) {
        issues.push({ severity: 'high', type: '悬空引用', tab: 'assess', targetId: a.id, detail: `题目「${a.code}」引用了不存在的目标 ${id}。`, suggestion: '修正引用或删除失效关联。' });
      }
    });
  });

  objectives.forEach((o) => {
    if (!asByObj[o.id].length) {
      issues.push({ severity: 'high', type: '目标缺评价', tab: 'design', targetId: o.id, detail: `${o.code}「${o.text.slice(0, 24)}…」没有任何题目挂接，无法验证达成情况。`, suggestion: `为该目标补充 1–2 道 A/B 层题目，并在题目中挂接 ${o.code}。` });
    }
    if (!segByObj[o.id].length) {
      issues.push({ severity: 'high', type: '目标缺活动', tab: 'design', targetId: o.id, detail: `${o.code} 未被任何教学环节覆盖，课堂上不会发生对应学习活动。`, suggestion: `在某一环节的「关联目标」中加入 ${o.code}，或补充专门活动。` });
    }
  });

  segments.forEach((s) => {
    if (!s.objectiveIds.length) {
      issues.push({ severity: 'medium', type: '环节未挂目标', tab: 'design', targetId: s.id, detail: `环节「${s.name}」没有关联任何教学目标，难以判断其必要性。`, suggestion: '明确该环节服务的目标，或将其合并到相邻环节。' });
    }
  });

  // 薄弱点覆盖
  const coveredKp = new Set();
  const addKps = (objectiveIds) => {
    objectiveIds.forEach((id) => {
      const o = objectives.find((x) => x.id === id);
      if (o) o.kpIds.forEach((k) => coveredKp.add(k));
    });
  };
  segments.forEach((s) => addKps(s.objectiveIds));
  assessments.forEach((a) => addKps(a.objectiveIds));
  (d.learner && d.learner.weak ? d.learner.weak : []).forEach((w) => {
    if (!coveredKp.has(w.kpId)) {
      issues.push({ severity: 'medium', type: '薄弱点未覆盖', tab: 'learner', targetId: w.kpId, detail: `学情薄弱点「${w.name}」没有被任何环节或题目命中。`, suggestion: '增加针对性活动或练习，并在题目中挂接对应目标。' });
    }
  });

  const rank = { high: 0, medium: 1, low: 2 };
  issues.sort((a, b) => rank[a.severity] - rank[b.severity]);

  const qualified = objectives.filter((o) => segByObj[o.id].length && asByObj[o.id].length).length;
  const total = objectives.length;
  const score = total ? Math.round((qualified / total) * 100) : 0;
  return { score, qualified, total, issues, segByObj, asByObj };
}

function scoreLevel(score) {
  if (score >= 90) return { label: '一致性优秀', color: 'var(--forest)', tone: 'good' };
  if (score >= 75) return { label: '基本一致，仍有断边', color: 'var(--gold)', tone: 'warn' };
  if (score >= 50) return { label: '一致性不足，建议修正', color: 'var(--clay)', tone: 'bad' };
  return { label: '关联严重缺失', color: 'var(--danger)', tone: 'bad' };
}

/* ---------------- 导出 Markdown ---------------- */

function toMarkdown(d, al) {
  const L = [];
  L.push(`# ${d.meta.topic} · 备课包`);
  L.push('');
  L.push(`> ${d.meta.stage} · ${d.meta.subject} · ${d.meta.periods} 学时 · 生成于 ${d.meta.createdAt}`);
  L.push('');
  L.push('## 一、课标条目与知识点');
  d.standards.forEach((s) => { L.push(`- **${s.code}**：${s.text}（来源：${s.source}）`); });
  L.push('');
  d.knowledge.forEach((k) => {
    const st = k.standardIds.map((id) => (d.standards.find((x) => x.id === id) || {}).code).filter(Boolean).join('、');
    L.push(`- 【${k.type}】${k.name} —— 挂接：${st || '待确认'}`);
  });
  L.push('');
  L.push('## 二、学情画像');
  if (d.learner.empty) L.push('> 未提供学情，以下为通用建议。');
  d.learner.weak.forEach((w) => L.push(`- **${w.name}**（${w.rate}）：${w.evidence}；建议：${w.suggestion}`));
  const sum = d.learner.dist.A + d.learner.dist.B + d.learner.dist.C;
  L.push('');
  L.push(`层次分布：A 层 ${d.learner.dist.A} 人 / B 层 ${d.learner.dist.B} 人 / C 层 ${d.learner.dist.C} 人（共 ${sum} 人）`);
  L.push('');
  L.push('## 三、教学目标与教学环节');
  d.objectives.forEach((o) => {
    const kps = o.kpIds.map((id) => (d.knowledge.find((x) => x.id === id) || {}).name).filter(Boolean).join('、');
    L.push(`- **${o.code}** ${o.text}${o.edited ? '（人工修改）' : ''}`);
    L.push(`  - 关联知识点：${kps || '待确认'}`);
  });
  L.push('');
  L.push('| 环节 | 时长 | 活动 | 关联目标 |');
  L.push('| --- | --- | --- | --- |');
  d.segments.forEach((s) => L.push(`| ${s.name} | ${s.minutes} 分钟 | ${s.activity} | ${s.objectiveIds.join('、') || '未挂接'} |`));
  L.push('');
  L.push('## 四、课件大纲与板书');
  d.slides.forEach((s, i) => {
    L.push(`### 第 ${i + 1} 页 · ${s.title}`);
    s.points.forEach((p) => L.push(`- ${p}`));
    if (s.note) L.push(`> 讲解备注：${s.note}`);
    L.push('');
  });
  L.push('**板书设计**');
  L.push('');
  L.push('```');
  L.push(d.board.text || '');
  L.push('```');
  L.push('');
  L.push('## 五、分层作业与评价量表');
  ['A', 'B', 'C'].forEach((lv) => {
    const items = d.assessments.filter((a) => a.level === lv);
    if (!items.length) return;
    L.push(`### ${lv} 层（${lv === 'A' ? '基础' : lv === 'B' ? '提升' : '拓展'}）`);
    items.forEach((a) => {
      L.push(`**${a.code}** ${a.stem}`);
      L.push(`- 答案：${a.answer}`);
      L.push(`- 关联目标：${a.objectiveIds.join('、') || '未挂接'}`);
      L.push('');
    });
  });
  L.push('### 评价量表');
  L.push('');
  L.push('| 维度 | 水平一 | 水平二 | 水平三 |');
  L.push('| --- | --- | --- | --- |');
  d.rubric.forEach((r) => L.push(`| ${r.dim} | ${r.levels[0]} | ${r.levels[1]} | ${r.levels[2]} |`));
  L.push('');
  L.push('## 六、教学评一致性');
  L.push('');
  L.push(`- 一致性得分：**${al.score} / 100**（合格目标 ${al.qualified} / ${al.total}）`);
  if (al.issues.length) {
    al.issues.forEach((i) => L.push(`- [${i.severity === 'high' ? '严重' : i.severity === 'medium' ? '中' : '低'}] ${i.type}：${i.detail} 建议：${i.suggestion}`));
  } else {
    L.push('- 未发现断边。');
  }
  L.push('');
  L.push('---');
  L.push('');
  L.push('## AIGC 使用标注');
  L.push('');
  L.push(`- 工具：智备 · 教师备课智能工作台（Demo v0.1，演示模式）`);
  L.push(`- 生成时间：${d.meta.createdAt}`);
  L.push('- 模型：本地演示引擎（模板化结构化生成，未调用云端大模型）');
  L.push(`- 提示词摘要：${d.meta.stage} / ${d.meta.subject} / ${d.meta.periods} 学时 / 课题「${d.meta.topic}」${d.learner.empty ? ' / 未提供学情' : ' / 已提供班级学情'}`);
  L.push(`- 人工修改：${state.editedCount} 处；锁定模块：${countLocked(d)} 个`);
  L.push('- 说明：本备课包包含 AI 生成内容，已经教师审核；课标条目为演示数据，正式使用需替换为权威来源。');
  return L.join('\n');
}

function countLocked(d) {
  if (!d) return 0;
  return [
    ...(d.objectives || []), ...(d.segments || []), ...(d.slides || []),
    ...(d.assessments || []), ...(d.knowledge || []), ...(d.standards || []),
  ].filter((x) => x.locked).length + (d.board && d.board.locked ? 1 : 0);
}
