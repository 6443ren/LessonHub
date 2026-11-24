"""
智备工作台 · 内置数据层
----------------------
- 课型 / 产出物 / 四层四翼标签等常量
- 内置课标库（演示用，注明来源）
- 带四层四翼标签的题库样例（30 题，支撑组卷演示）
- 七种课型的预设样例（无 API Key 或生成失败时降级使用）
"""

# ---------------------------------------------------------------- 常量

LESSON_TYPES = [
    {'key': '新课', 'label': '新课', 'desc': '依据课标与教材生成全套新课材料', 'icon': 'book'},
    {'key': '习题课', 'label': '习题课', 'desc': '讲评试卷/错题，归类错因并变式训练', 'icon': 'pen'},
    {'key': '复习课', 'label': '复习课', 'desc': '梳理知识框架，专题复习与综合训练', 'icon': 'repeat'},
    {'key': '答疑课', 'label': '答疑课', 'desc': '归类学生问题，精讲与针对性跟进', 'icon': 'help'},
    {'key': '班会课', 'label': '班会课', 'desc': '班级活动方案、串词与素材清单', 'icon': 'users'},
    {'key': '心理课', 'label': '心理课', 'desc': '活动体验、分享引导与心理知识要点', 'icon': 'heart'},
    {'key': '其他', 'label': '其他', 'desc': '自定义课型名称与要求，通用框架适配', 'icon': 'plus'},
]

OUTPUTS = [
    {'key': 'schedule', 'label': '教学计划', 'desc': '单元/课时整体规划与课时分配表'},
    {'key': 'plan', 'label': '完整教案', 'desc': '目标、重难点、过程、板书、作业、反思'},
    {'key': 'slides', 'label': 'PPT', 'desc': '逐页大纲、配图建议、演讲提示'},
    {'key': 'homework', 'label': '作业', 'desc': '基础/提升/拓展三层题 + 答案解析'},
]

# 考试评价规范层（§5.3 一核四层四翼）
FOUR_WINGS = ['基础性', '综合性', '应用性', '创新性']
FOUR_LAYERS = ['核心价值', '学科素养', '关键能力', '必备知识']
CONTEXT_TYPES = ['学业情境', '生活情境', '科学探究情境', '学科传统文化情境']

DIFFICULTIES = ['基础', '提升', '拓展']
QUESTION_TYPES = ['选择题', '填空题', '解答题']


# ---------------------------------------------------------------- 内置课标库（演示用）

STANDARDS = {
    '数学': [
        {'id': 'G4-2-03', 'code': '图形与几何·图形的性质', 'text': '探索并证明三角形的内角和定理', 'source': '《义务教育数学课程标准（2022年版）》', 'kps': ['三角形内角和']},
        {'id': 'G4-2-04', 'code': '图形与几何·图形的性质', 'text': '掌握三角形全等的判定方法（SSS/SAS/ASA/AAS/HL）', 'source': '《义务教育数学课程标准（2022年版）》', 'kps': ['全等三角形']},
        {'id': 'A3-1-02', 'code': '数与代数·函数', 'text': '结合具体情境体会一次函数的意义，能画出一次函数的图象', 'source': '《义务教育数学课程标准（2022年版）》', 'kps': ['一次函数']},
        {'id': 'A3-2-03', 'code': '数与代数·函数', 'text': '通过对实际问题的分析，体会二次函数的意义', 'source': '《义务教育数学课程标准（2022年版）》', 'kps': ['二次函数']},
    ],
    '物理': [
        {'id': 'P-M-01', 'code': '机械运动与力', 'text': '理解牛顿运动定律，能用其分析与解决简单的力学问题', 'source': '《普通高中物理课程标准（2017年版2020年修订）》', 'kps': ['牛顿运动定律']},
        {'id': 'P-M-02', 'code': '相互作用', 'text': '能进行受力分析，理解力的合成与分解', 'source': '《普通高中物理课程标准（2017年版2020年修订）》', 'kps': ['受力分析']},
    ],
    '生物': [
        {'id': 'B-C-01', 'code': '细胞', 'text': '说明细胞的基本结构及各部分功能', 'source': '《义务教育生物学课程标准（2022年版）》', 'kps': ['细胞结构']},
    ],
}


# ---------------------------------------------------------------- 题库样例（带四层四翼标签，30 题）

def _q(qid, stem, answer, kps, diff, qtype, wings, layers, ctx, score=5, source='内置题库', subject=None):
    q = {
        'qid': qid, 'stem': stem, 'answer': answer, 'knowledge_points': kps,
        'difficulty': diff, 'question_type': qtype, 'score': score, 'source': source,
        'assessment_tags': {'four_wings': wings, 'four_layers': layers, 'context_type': ctx},
    }
    if subject:
        q['subject'] = subject
    return q

# 批量给题库按知识点注入学科（避免每个 _q 都手写 subject=）
def _tag_subject(bank, kp_to_subject):
    for q in bank:
        if 'subject' in q:
            continue
        for kp in q.get('knowledge_points', []):
            if kp in kp_to_subject:
                q['subject'] = kp_to_subject[kp]
                break
    return bank


QUESTION_BANK = [
    # —— 三角形内角和（6 题）——
    _q('Q001', '已知三角形两个内角分别为 50° 和 60°，第三个角为（  ）\nA. 60°  B. 70°  C. 80°  D. 90°', 'B. 70°', ['三角形内角和'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q002', '在△ABC 中，∠A=35°，∠B=65°，则∠C=____。', '80°', ['三角形内角和'], '基础', '填空题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q003', '等腰三角形的一个内角为 70°，求另外两个内角的度数。', '70°、40° 或 55°、55°（需分类讨论）', ['三角形内角和'], '提升', '解答题', ['综合性'], ['关键能力'], '学业情境', 6),
    _q('Q004', '证明：三角形三个内角的和等于 180°。（要求：写出已知、求证并证明）', '过顶点作平行线，利用内错角转化为平角', ['三角形内角和'], '提升', '解答题', ['综合性'], ['关键能力', '学科素养'], '学业情境', 8),
    _q('Q005', '一块三角形零件缺了一个角，测得剩余两角分别为 45° 和 60°，能否确定缺角的大小？说明理由。', '能，75°；三角形内角和为定值，与形状无关', ['三角形内角和'], '拓展', '解答题', ['应用性', '创新性'], ['学科素养'], '生活情境', 8),
    _q('Q006', '在△ABC 中，∠A 的外角等于 120°，∠B=50°，求∠C。', '70°', ['三角形内角和'], '提升', '填空题', ['综合性'], ['关键能力'], '学业情境', 4),
    # —— 全等三角形（5 题）——
    _q('Q007', '下列条件中，不能判定两个三角形全等的是（  ）\nA. SSS  B. SAS  C. SSA  D. ASA', 'C', ['全等三角形'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q008', '已知 AB=A\'B\'，∠A=∠A\'，要使△ABC≌△A\'B\'C\'，还需添加的一个条件是____。', 'AC=A\'C\'（SAS）或 ∠B=∠B\'（ASA）', ['全等三角形'], '提升', '填空题', ['综合性'], ['关键能力'], '学业情境', 4),
    _q('Q009', '如图，AB=AD，BC=DC，求证：∠B=∠D。', '连接 AC，由 SSS 证△ABC≌△ADC', ['全等三角形'], '提升', '解答题', ['综合性'], ['关键能力'], '学业情境', 7),
    _q('Q010', '用尺规作一个角等于已知角，其依据的三角形全等判定方法是____。', 'SSS', ['全等三角形'], '基础', '填空题', ['基础性'], ['必备知识'], '科学探究情境', 3),
    _q('Q011', '测量河两岸两点 A、B 的距离：在岸边取点 C，构造全等三角形间接测量。请设计方案并说明依据。', '构造 SAS 全等，对应边相等', ['全等三角形'], '拓展', '解答题', ['应用性', '创新性'], ['学科素养', '核心价值'], '生活情境', 9),
    # —— 一次函数（5 题）——
    _q('Q012', '一次函数 y=2x-3 的图象与 y 轴的交点坐标是（  ）\nA. (0,-3)  B. (0,3)  C. (-3,0)  D. (3,0)', 'A', ['一次函数'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q013', '直线 y=kx+b 经过点 (1,3) 和 (0,1)，则 k=____，b=____。', 'k=2，b=1', ['一次函数'], '基础', '填空题', ['基础性'], ['关键能力'], '学业情境', 4),
    _q('Q014', '已知一次函数 y=(m-1)x+2，y 随 x 增大而减小，求 m 的取值范围。', 'm<1', ['一次函数'], '提升', '解答题', ['综合性'], ['关键能力'], '学业情境', 5),
    _q('Q015', '某商店会员卡工本费 20 元，凭卡购物打 8 折。设购物原价 x 元，实付 y 元，写出 y 关于 x 的函数关系式，并计算购物 200 元时实付多少。', 'y=0.8x+20；180 元', ['一次函数'], '提升', '解答题', ['应用性'], ['关键能力'], '生活情境', 7),
    _q('Q016', '甲、乙两车从 A 地出发，路程 s 与时间 t 的函数图象交于一点。解释交点的实际意义，并比较两车速度。', '交点表示相遇时刻；斜率大者速度大', ['一次函数'], '拓展', '解答题', ['综合性', '创新性'], ['学科素养'], '科学探究情境', 8),
    # —— 二次函数（4 题）——
    _q('Q017', '抛物线 y=x²-4x+3 的顶点坐标是（  ）\nA. (2,-1)  B. (-2,1)  C. (2,1)  D. (-2,-1)', 'A', ['二次函数'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q018', '二次函数 y=ax²+bx+c 的图象开口向下，对称轴为 x=1，则 a____0，b____0。', 'a<0，b<0', ['二次函数'], '提升', '填空题', ['综合性'], ['关键能力'], '学业情境', 4),
    _q('Q019', '用长 20 m 的篱笆围成一面靠墙的矩形花圃，设宽为 x m，求面积 S 关于 x 的函数关系式及最大面积。', 'S=x(20-2x)=-2x²+20x，x=5 时最大 50 m²', ['二次函数'], '拓展', '解答题', ['应用性', '创新性'], ['学科素养'], '生活情境', 9),
    _q('Q020', '已知二次函数 y=x²-2x-3，求它与 x 轴的交点坐标及当 y<0 时 x 的取值范围。', '交点 (-1,0),(3,0)；-1<x<3', ['二次函数'], '提升', '解答题', ['综合性'], ['关键能力'], '学业情境', 6),
    # —— 牛顿运动定律（5 题）——
    _q('Q021', '关于牛顿第一定律，下列说法正确的是（  ）\nA. 物体不受力时一定静止  B. 力是维持运动的原因  C. 物体运动状态改变一定受力  D. 惯性是一种力', 'C', ['牛顿运动定律'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q022', '质量为 2 kg 的物体在水平面上受 6 N 水平拉力，加速度为 2 m/s²，则摩擦力为____N。', '2 N', ['牛顿运动定律'], '基础', '填空题', ['基础性'], ['关键能力'], '学业情境', 4),
    _q('Q023', '电梯以 a=2 m/s² 加速上升时，质量 50 kg 的人对地板的压力为多大？（g 取 10）', '600 N（超重）', ['牛顿运动定律'], '提升', '解答题', ['综合性'], ['关键能力'], '生活情境', 6),
    _q('Q024', '光滑水平面上 A、B 两物体用绳连接，质量分别为 2 kg、3 kg，在 10 N 水平拉力作用下一起运动，求加速度及绳中张力。', 'a=2 m/s²；张力 6 N', ['牛顿运动定律'], '提升', '解答题', ['综合性'], ['关键能力'], '科学探究情境', 7),
    _q('Q025', '为什么汽车突然启动时乘客会后仰，而紧急刹车时会前倾？请用惯性知识解释。', '启动时下半身随车加速、上半身保持原静止状态；刹车时相反', ['牛顿运动定律'], '拓展', '解答题', ['应用性', '创新性'], ['核心价值', '学科素养'], '生活情境', 6),
    # —— 受力分析（3 题）——
    _q('Q026', '静止在斜面上的物体受到的力是（  ）\nA. 重力、支持力  B. 重力、支持力、摩擦力  C. 重力、下滑力  D. 重力、支持力、下滑力', 'B', ['受力分析'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q027', '把一个 5 N 的物体用 20 N 的水平力压在竖直墙壁上保持静止，求摩擦力的大小和方向。', '5 N，竖直向上', ['受力分析'], '提升', '解答题', ['综合性'], ['关键能力'], '学业情境', 6),
    _q('Q028', '两物块叠放一起在水平面上向右匀速运动，分析上下两物块各自的受力情况。', '上：重力、支持力（无摩擦）；下：重力、支持力、上物压力、地面摩擦', ['受力分析'], '拓展', '解答题', ['综合性', '创新性'], ['学科素养'], '科学探究情境', 8),
    # —— 细胞结构（2 题）——
    _q('Q029', '植物细胞特有的结构是（  ）\nA. 细胞膜  B. 细胞核  C. 叶绿体  D. 线粒体', 'C', ['细胞结构'], '基础', '选择题', ['基础性'], ['必备知识'], '学业情境', 3),
    _q('Q030', '比较动物细胞与植物细胞在结构上的异同点，并说明细胞膜的功能。', '共同点：细胞膜、细胞质、细胞核；植物特有：细胞壁、叶绿体、液泡；细胞膜控制物质进出', ['细胞结构'], '提升', '解答题', ['综合性'], ['关键能力'], '科学探究情境', 7),
]

# 给每道题注入学科（按知识点映射）
_kp_subject = {
    '三角形内角和': '数学', '全等三角形': '数学',
    '一次函数': '数学', '二次函数': '数学',
    '牛顿运动定律': '物理', '受力分析': '物理',
    '细胞结构': '生物',
}
_tag_subject(QUESTION_BANK, _kp_subject)


# ---------------------------------------------------------------- 预设样例（降级用）

def _base(lesson_type, topic, stage, subject):
    return {
        'lesson_type': lesson_type,
        'custom_type_name': '',
        'lesson_period': {'index': 1, 'total': 1, 'minutes': 45},
        'teaching_schedule': {'unit_theme': topic, 'objectives': [], 'period_allocation': [], 'assessment': '', 'resources': []},
        'teaching_plan': {'objectives': [], 'key_points': [], 'difficult_points': [], 'process': [], 'board_design': '', 'homework': '', 'reflection': ''},
        'slides': [],
        'homework': [],
        'evidence': [],
        'disclaimer': '本材料为 AI 生成初稿，请教师审核修改后使用。',
        'subject': subject,
        'stage': stage,
        'topic': topic,
    }


SAMPLE_NEW = {
    **_base('新课', '三角形内角和定理', '义务教育', '数学'),
    'lesson_period': {'index': 1, 'total': 3, 'minutes': 45},
    'teaching_schedule': {
        'unit_theme': '三角形',
        'objectives': ['理解三角形内角和定理并能证明', '能运用定理进行角度计算与推理', '经历操作—猜想—证明的探究过程'],
        'period_allocation': [
            {'index': 1, 'topic': '三角形内角和定理的探究与证明', 'key_points': '内角和定理', 'difficult_points': '辅助线作法与转化思想', 'minutes': 45},
            {'index': 2, 'topic': '内角和定理的应用与外角性质', 'key_points': '定理应用', 'difficult_points': '复杂图形中的识别与运用', 'minutes': 45},
            {'index': 3, 'topic': '单元综合与习题讲评', 'key_points': '综合运用', 'difficult_points': '易错点归类与变式', 'minutes': 45},
        ],
        'assessment': '每课时当堂检测 2–3 题，第 3 课时单元小测。',
        'resources': ['量角器', '剪刀', '多媒体课件'],
    },
    'teaching_plan': {
        'objectives': ['经历撕角拼角操作，猜想并证明三角形内角和为 180°', '能运用内角和定理进行简单计算与推理', '体会转化思想，发展几何直观与推理能力'],
        'key_points': ['内角和定理的探究与证明'],
        'difficult_points': ['辅助线的作法', '转化思想的理解'],
        'process': [
            {'stage': '情境导入', 'minutes': 5, 'activity': '呈现三角形模具，提问内角和', 'teacher': '引导观察与提问', 'student': '观察、猜想'},
            {'stage': '操作猜想', 'minutes': 10, 'activity': '量角器测量、撕角拼合', 'teacher': '巡视指导', 'student': '动手操作、记录数据'},
            {'stage': '证明探究', 'minutes': 15, 'activity': '作平行线辅助线证明', 'teacher': '示范作辅助线', 'student': '书写证明过程'},
            {'stage': '巩固应用', 'minutes': 10, 'activity': '例题与当堂检测', 'teacher': '点评纠错', 'student': '独立完成'},
            {'stage': '小结作业', 'minutes': 5, 'activity': '梳理思路、布置作业', 'teacher': '总结方法', 'student': '整理笔记'},
        ],
        'board_design': '三角形内角和定理\n猜想：∠A+∠B+∠C=180°\n证明：作辅助平行线 → 转化为平角\n应用：已知两角求第三角',
        'homework': '基础 2 题、提升 1 题、拓展 1 题',
        'reflection': '关注学生是否真正理解辅助线的必要性，而非机械记忆结论。',
    },
    'slides': [
        {'page': 1, 'title': '三角形内角和定理', 'bullets': ['第 1 课时', '探究与证明'], 'image_suggestion': '三角形模具实物图', 'speaker_notes': '从生活中的三角形引入'},
        {'page': 2, 'title': '情境与问题', 'bullets': ['三角形三个内角的和是多少？', '如何验证？'], 'image_suggestion': '量角器测量示意图', 'speaker_notes': ''},
        {'page': 3, 'title': '操作探究', 'bullets': ['测量法', '撕角拼合法'], 'image_suggestion': '撕角拼成平角动画', 'speaker_notes': '让学生动手操作'},
        {'page': 4, 'title': '定理证明', 'bullets': ['过顶点作平行线', '内错角转化', '平角 = 180°'], 'image_suggestion': '辅助线作图', 'speaker_notes': '强调转化思想'},
        {'page': 5, 'title': '例题与检测', 'bullets': ['已知两角求第三角', '分类讨论：等腰三角形'], 'image_suggestion': '', 'speaker_notes': '当堂检测 2 题'},
        {'page': 6, 'title': '小结与作业', 'bullets': ['定理内容', '证明方法', '作业布置'], 'image_suggestion': '', 'speaker_notes': ''},
    ],
    'homework': [
        {'level': '基础', 'questions': ['已知三角形两角为 45° 和 60°，求第三角。', '判断：三角形三个内角中至少有两个锐角。'], 'answers': ['75°', '正确']},
        {'level': '提升', 'questions': ['等腰三角形一个内角为 80°，求另外两角。'], 'answers': ['80°、20° 或 50°、50°']},
        {'level': '拓展', 'questions': ['探究四边形内角和，写出你的方法。'], 'answers': ['连接一条对角线，转化为两个三角形，和为 360°']},
    ],
    'evidence': [
        {'source': '课标 G4-2-03：探索并证明三角形的内角和定理', 'used_in': '教学目标、教学过程'},
        {'source': '模型归纳，待教师核对', 'used_in': '例题数据'},
    ],
}

SAMPLE_REVIEW = {
    **_base('复习课', '牛顿运动定律专题复习', '普通高中', '物理'),
    'lesson_period': {'index': 2, 'total': 2, 'minutes': 45},
    'teaching_schedule': {
        'unit_theme': '力学（牛顿运动定律）',
        'objectives': ['梳理牛顿三定律的关系网络', '掌握受力分析与连接体问题解法', '识别临界问题并分析'],
        'period_allocation': [
            {'index': 1, 'topic': '知识框架梳理与基础回顾', 'key_points': '牛顿三定律关系', 'difficult_points': '概念辨析', 'minutes': 45},
            {'index': 2, 'topic': '专题复习：受力分析、连接体、临界问题', 'key_points': '三类题型解法', 'difficult_points': '临界条件分析', 'minutes': 45},
        ],
        'assessment': '综合训练卷（90 分钟）+ 双向细目表',
        'resources': ['力学单元测试卷（教师上传）', '多媒体课件'],
    },
    'teaching_plan': {
        'objectives': ['能画出牛顿三定律关系图并说明逻辑', '掌握受力分析、连接体、临界问题三类题型解法', '能从错因角度归纳薄弱点'],
        'key_points': ['三类题型的解题方法'],
        'difficult_points': ['临界条件的识别与分析'],
        'process': [
            {'stage': '框架梳理', 'minutes': 10, 'activity': '师生共建知识网络', 'teacher': '引导归纳', 'student': '补充完善导图'},
            {'stage': '专题一 受力分析', 'minutes': 10, 'activity': '讲评典型错题', 'teacher': '强调隔离法', 'student': '订正并归纳'},
            {'stage': '专题二 连接体', 'minutes': 10, 'activity': '整体法与隔离法对比', 'teacher': '板书推导', 'student': '模仿练习'},
            {'stage': '专题三 临界问题', 'minutes': 10, 'activity': '临界条件分析', 'teacher': '点拨思路', 'student': '小组讨论'},
            {'stage': '小结与训练', 'minutes': 5, 'activity': '布置综合训练卷', 'teacher': '说明评价方式', 'student': '记录要求'},
        ],
        'board_design': '牛顿运动定律复习\n一核：运动与力的关系\n框架：定律①②③ → 受力分析 → 连接体 → 临界',
        'homework': '综合训练卷（教师上传试卷变式 + 新题）',
        'reflection': '连接体问题需反复训练整体—隔离的切换意识。',
    },
    'slides': [
        {'page': 1, 'title': '牛顿运动定律专题复习', 'bullets': ['第 2 课时 / 共 2 课时'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 2, 'title': '知识框架', 'bullets': ['牛顿三定律关系图'], 'image_suggestion': '关系网络图', 'speaker_notes': ''},
        {'page': 3, 'title': '专题一 受力分析', 'bullets': ['隔离法', '常见错因'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 4, 'title': '专题二 连接体', 'bullets': ['整体法', '隔离法', '张力求解'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 5, 'title': '专题三 临界问题', 'bullets': ['临界条件识别'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 6, 'title': '考情解读与训练', 'bullets': ['四翼配比：基础 40% / 综合 30% / 应用 20% / 创新 10%', '综合训练卷'], 'image_suggestion': '', 'speaker_notes': '引用高考评价体系'},
    ],
    'homework': [
        {'level': '基础', 'questions': ['受力分析 2 题', '牛顿第二定律基本计算 2 题'], 'answers': ['见综合训练卷答案']},
        {'level': '提升', 'questions': ['连接体问题 2 题'], 'answers': ['见综合训练卷答案']},
        {'level': '拓展', 'questions': ['临界问题 1 题'], 'answers': ['见综合训练卷答案']},
    ],
    'evidence': [
        {'source': '课标 P-M-01：理解牛顿运动定律', 'used_in': '复习目标与命题方向'},
        {'source': '教师上传资料：力学单元测试卷（解析出 18 道题）', 'used_in': '错题归类与变式训练'},
        {'source': '《中国高考评价体系》一核四层四翼', 'used_in': '考情解读页与组卷配比'},
    ],
}

SAMPLE_EXERCISE = {
    **_base('习题课', '一次函数错题讲评', '义务教育', '数学'),
    'teaching_plan': {
        'objectives': ['归类一次函数常见错因', '掌握待定系数法与图象法', '能进行变式迁移'],
        'key_points': ['错因归类', '变式训练'],
        'difficult_points': ['k、b 符号与图象位置的关系'],
        'process': [
            {'stage': '错题归类', 'minutes': 12, 'activity': '按知识点统计高频错因', 'teacher': '展示统计', 'student': '认领错因'},
            {'stage': '重点讲评', 'minutes': 15, 'activity': '讲评 3 道典型题', 'teacher': '追问思路', 'student': '讲解互评'},
            {'stage': '变式训练', 'minutes': 13, 'activity': '同结构变式题练习', 'teacher': '巡视', 'student': '独立完成'},
            {'stage': '小结巩固', 'minutes': 5, 'activity': '归纳方法、布置作业', 'teacher': '总结', 'student': '整理'},
        ],
        'board_design': '一次函数错题讲评\n错因：①k、b 符号 ②待定系数 ③实际意义\n方法：图象法 → 待定系数法',
        'homework': '变式巩固 4 题',
        'reflection': '讲评后要让学生用自己的话复述解题路径。',
    },
    'evidence': [{'source': '教师上传试卷：一次函数单元测', 'used_in': '错题归类'}],
}

SAMPLE_QA = {
    **_base('答疑课', '二次函数疑点解答', '义务教育', '数学'),
    'teaching_plan': {
        'objectives': ['归类二次函数典型疑点', '精讲顶点、对称轴、最值', '提供针对性跟进练习'],
        'key_points': ['疑点归类', '方法精讲'],
        'difficult_points': ['最值在区间上的讨论'],
        'process': [
            {'stage': '问题归类', 'minutes': 10, 'activity': '汇总学生问题清单', 'teacher': '分类板书', 'student': '提交问题'},
            {'stage': '精讲', 'minutes': 20, 'activity': '逐一精讲 3 类疑点', 'teacher': '板书演示', 'student': '记录追问'},
            {'stage': '跟进练习', 'minutes': 10, 'activity': '针对性练习', 'teacher': '面批', 'student': '完成'},
            {'stage': '小结', 'minutes': 5, 'activity': '归纳方法卡', 'teacher': '总结', 'student': '整理'},
        ],
        'board_design': '二次函数答疑\n疑点：①顶点坐标 ②对称轴 ③区间最值\n方法卡：配方法 / 公式法',
        'homework': '针对性跟进 3 题',
        'reflection': '对反复出错的学生提供步骤卡。',
    },
    'evidence': [{'source': '学生问题清单（教师录入）', 'used_in': '问题归类'}],
}

SAMPLE_CLASS_MEETING = {
    **_base('班会课', '手机管理的班级共识', '义务教育', '综合'),
    'teaching_plan': {
        'objectives': ['通过讨论形成手机使用班级共识', '提升自我管理与规则意识', '产出可执行的班级公约'],
        'key_points': ['共识形成', '公约制定'],
        'difficult_points': ['引导理性表达而非对立'],
        'process': [
            {'stage': '暖场', 'minutes': 5, 'activity': '呈现校园手机使用现象', 'teacher': '播放情境', 'student': '观察感受'},
            {'stage': '情境讨论', 'minutes': 12, 'activity': '小组讨论利弊', 'teacher': '巡视引导', 'student': '小组交流'},
            {'stage': '小组辩论', 'minutes': 15, 'activity': '正方反方辩论', 'teacher': '主持规则', 'student': '辩论'},
            {'stage': '公约制定', 'minutes': 10, 'activity': '共同拟定公约条款', 'teacher': '记录整理', 'student': '提议表决'},
            {'stage': '总结承诺', 'minutes': 3, 'activity': '签字承诺', 'teacher': '强调自律', 'student': '签字'},
        ],
        'board_design': '手机管理班级共识\n利：学习工具 / 弊：分心依赖\n公约：①入班集中管理 ②课间限时 ③作业不搜答案',
        'homework': '完善个人手机使用承诺书',
        'reflection': '本方案为活动参考，现场引导需教师把控价值导向。',
    },
    'slides': [
        {'page': 1, 'title': '手机管理的班级共识', 'bullets': ['主题班会'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 2, 'title': '情境导入', 'bullets': ['校园手机现象'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 3, 'title': '小组讨论', 'bullets': ['利弊分析'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 4, 'title': '公约制定', 'bullets': ['共同拟定条款'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 5, 'title': '承诺签字', 'bullets': ['班级共识'], 'image_suggestion': '', 'speaker_notes': ''},
    ],
    'evidence': [{'source': '班级情况（教师录入）', 'used_in': '活动方案'}],
}

SAMPLE_PSYCHOLOGY = {
    **_base('心理课', '青春期情绪管理', '义务教育', '心理健康'),
    'teaching_plan': {
        'objectives': ['识别常见情绪及其生理信号', '练习情绪调节的简单方法', '学会向他人表达与求助'],
        'key_points': ['情绪识别', '调节方法'],
        'difficult_points': ['引导分享而非强迫表达'],
        'process': [
            {'stage': '暖场活动', 'minutes': 8, 'activity': '情绪猜猜看', 'teacher': '组织游戏', 'student': '参与体验'},
            {'stage': '体验练习', 'minutes': 12, 'activity': '画出最近的一种情绪', 'teacher': '陪伴引导', 'student': '绘制感受'},
            {'stage': '分享讨论', 'minutes': 12, 'activity': '自愿分享', 'teacher': '共情回应', 'student': '自愿分享'},
            {'stage': '知识提炼', 'minutes': 8, 'activity': '讲解情绪调节方法', 'teacher': '讲授方法', 'student': '记录方法卡'},
            {'stage': '课后延伸', 'minutes': 5, 'activity': '布置情绪日记', 'teacher': '说明注意事项', 'student': '记录'},
        ],
        'board_design': '青春期情绪管理\n情绪：喜怒哀惧\n调节：深呼吸 / 运动 / 倾诉 / 求助\n⚠ 识别危机信号 → 转介专业心理教师',
        'homework': '连续 3 天记录情绪日记',
        'reflection': '不作诊断性判断；出现自伤等信号时提示转介。',
    },
    'evidence': [{'source': '年龄段：初二（教师录入）', 'used_in': '活动设计'}],
}

SAMPLE_OTHER = {
    **_base('其他', '校园垃圾分类现状调查', '义务教育', '综合实践'),
    'custom_type_name': '综合实践活动课',
    'lesson_period': {'index': 1, 'total': 1, 'minutes': 90},
    'teaching_plan': {
        'objectives': ['以小组项目形式开展校园垃圾分类调查', '完成任务分工与调查方法学习', '了解外出安全规范'],
        'key_points': ['项目式学习框架', '任务分工'],
        'difficult_points': ['调查方法的指导'],
        'process': [
            {'stage': '问题提出', 'minutes': 10, 'activity': '明确驱动问题', 'teacher': '呈现校园垃圾现状', 'student': '提出问题'},
            {'stage': '分组分工', 'minutes': 15, 'activity': '组建小组、明确角色', 'teacher': '指导分工', 'student': '认领角色'},
            {'stage': '调查方法指导', 'minutes': 25, 'activity': '讲解观察、访谈、记录方法', 'teacher': '示范记录模板', 'student': '练习填写'},
            {'stage': '成果预设', 'minutes': 20, 'activity': '规划成果形式', 'teacher': '提供量规', 'student': '规划展示'},
            {'stage': '安全提示与评价', 'minutes': 20, 'activity': '外出安全说明 + 评价量规', 'teacher': '强调纪律安全', 'student': '确认承诺'},
        ],
        'board_design': '综合实践：校园垃圾分类调查\n框架：问题→分工→方法→成果→评价\n安全：外出结伴、报告去向、按时返校',
        'homework': '',
        'reflection': '实践活动以过程性评价为主，关注分工协作与安全意识。',
    },
    'slides': [
        {'page': 1, 'title': '校园垃圾分类现状调查', 'bullets': ['综合实践活动课', '90 分钟连堂'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 2, 'title': '驱动问题', 'bullets': ['校园垃圾分类现状如何？'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 3, 'title': '分组任务表', 'bullets': ['角色分工模板'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 4, 'title': '调查记录表', 'bullets': ['观察 / 访谈记录模板'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 5, 'title': '安全提示', 'bullets': ['外出安全规范'], 'image_suggestion': '', 'speaker_notes': ''},
        {'page': 6, 'title': '评价量规', 'bullets': ['过程性 + 成果性评价'], 'image_suggestion': '', 'speaker_notes': ''},
    ],
    'evidence': [{'source': '自定义要求：小组项目、任务分工、外出安全提示、只生成教案和PPT', 'used_in': '产出控制'}],
}

PRESET_SAMPLES = {
    '新课': SAMPLE_NEW,
    '习题课': SAMPLE_EXERCISE,
    '复习课': SAMPLE_REVIEW,
    '答疑课': SAMPLE_QA,
    '班会课': SAMPLE_CLASS_MEETING,
    '心理课': SAMPLE_PSYCHOLOGY,
    '其他': SAMPLE_OTHER,
}
