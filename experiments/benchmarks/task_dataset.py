"""
评测任务数据集模块
提供标准化的评测任务加载与管理
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import json
from enum import Enum

class TaskType(Enum):
    CODE_GENERATION = "code_generation"
    BUG_FIX = "bug_fix"
    REQUIREMENT_DECOMPOSITION = "requirement_decomposition"

@dataclass
class EvaluationTask:
    """评测任务结构体"""
    task_id: str
    task_type: TaskType
    name: str
    description: str
    requirement: str
    test_cases: List[Dict[str, Any]]
    expected_output: Optional[str] = None
    difficulty: int = 3  # 1-5，难度从低到高
    domain_tags: List[str] = None
    metadata: Dict[str, Any] = None

class TaskDataset:
    """评测任务数据集类"""
    def __init__(self):
        self.tasks: Dict[str, EvaluationTask] = {}
    
    def add_task(self, task: EvaluationTask) -> None:
        """添加任务到数据集"""
        self.tasks[task.task_id] = task
    
    def get_task(self, task_id: str) -> Optional[EvaluationTask]:
        """根据ID获取任务"""
        return self.tasks.get(task_id)
    
    def filter_by_type(self, task_type: TaskType) -> List[EvaluationTask]:
        """按任务类型筛选"""
        return [t for t in self.tasks.values() if t.task_type == task_type]
    
    def filter_by_difficulty(self, min_diff: int, max_diff: int) -> List[EvaluationTask]:
        """按难度筛选"""
        return [t for t in self.tasks.values() if min_diff <= t.difficulty <= max_diff]
    
    def get_all_tasks(self) -> List[EvaluationTask]:
        """获取所有任务"""
        return list(self.tasks.values())
    
    def load_sample_tasks(self) -> None:
        """加载示例测试任务，用于快速验证"""
        # ==================== 代码生成任务 (20+) ====================
        code_gen_tasks = [
            EvaluationTask(
                task_id="cg_001",
                task_type=TaskType.CODE_GENERATION,
                name="快速排序实现",
                description="实现Python快速排序函数",
                requirement="写一个Python函数实现快速排序，支持整数列表排序，返回升序排列结果",
                test_cases=[
                    {"input": [3,1,4,1,5,9,2,6], "expected": [1,1,2,3,4,5,6,9]},
                    {"input": [], "expected": []},
                    {"input": [5,4,3,2,1], "expected": [1,2,3,4,5]}
                ],
                difficulty=2,
                domain_tags=["Python", "算法", "排序"]
            ),
            EvaluationTask(
                task_id="cg_002",
                task_type=TaskType.CODE_GENERATION,
                name="斐波那契数列",
                description="实现斐波那契数列计算函数",
                requirement="写一个Python函数计算第n个斐波那契数，n从0开始，F(0)=0, F(1)=1",
                test_cases=[
                    {"input": 0, "expected": 0},
                    {"input": 1, "expected": 1},
                    {"input": 10, "expected": 55}
                ],
                difficulty=1,
                domain_tags=["Python", "算法"]
            ),
            EvaluationTask(
                task_id="cg_003",
                task_type=TaskType.CODE_GENERATION,
                name="二分查找",
                description="实现二分查找算法",
                requirement="实现一个二分查找函数，在已排序列表中查找目标元素，返回索引或-1",
                test_cases=[
                    {"input": ([1,2,3,4,5], 3), "expected": 2},
                    {"input": ([1,2,3,4,5], 6), "expected": -1},
                    {"input": ([], 1), "expected": -1}
                ],
                difficulty=2,
                domain_tags=["Python", "算法", "查找"]
            ),
            EvaluationTask(
                task_id="cg_004",
                task_type=TaskType.CODE_GENERATION,
                name="链表反转",
                description="实现单链表反转",
                requirement="实现一个函数反转单链表，返回反转后的头节点",
                test_cases=[
                    {"input": [1,2,3,4,5], "expected": [5,4,3,2,1]},
                    {"input": [1], "expected": [1]},
                    {"input": [], "expected": []}
                ],
                difficulty=2,
                domain_tags=["Python", "算法", "链表"]
            ),
            EvaluationTask(
                task_id="cg_005",
                task_type=TaskType.CODE_GENERATION,
                name="字符串反转",
                description="实现字符串反转函数",
                requirement="实现一个函数反转输入字符串，不使用内置reverse方法",
                test_cases=[
                    {"input": "hello", "expected": "olleh"},
                    {"input": "a", "expected": "a"},
                    {"input": "", "expected": ""}
                ],
                difficulty=1,
                domain_tags=["Python", "字符串"]
            ),
            EvaluationTask(
                task_id="cg_006",
                task_type=TaskType.CODE_GENERATION,
                name="判断回文数",
                description="判断一个整数是否为回文数",
                requirement="实现函数判断整数是否为回文数（正读和倒读相同），负数返回False",
                test_cases=[
                    {"input": 121, "expected": True},
                    {"input": -121, "expected": False},
                    {"input": 10, "expected": False}
                ],
                difficulty=2,
                domain_tags=["Python", "数学"]
            ),
            EvaluationTask(
                task_id="cg_007",
                task_type=TaskType.CODE_GENERATION,
                name="两数之和",
                description="查找数组中两数之和为目标值的索引",
                requirement="给定整数数组和目标值，返回两个数的索引使得它们的和为目标值",
                test_cases=[
                    {"input": ([2,7,11,15], 9), "expected": [0,1]},
                    {"input": ([3,2,4], 6), "expected": [1,2]}
                ],
                difficulty=2,
                domain_tags=["Python", "算法", "数组"]
            ),
            EvaluationTask(
                task_id="cg_008",
                task_type=TaskType.CODE_GENERATION,
                name="合并两个有序链表",
                description="合并两个有序链表",
                requirement="实现函数合并两个有序链表，返回合并后的有序链表",
                test_cases=[
                    {"input": ([1,2,4], [1,3,4]), "expected": [1,1,2,3,4,4]},
                    {"input": ([], []), "expected": []}
                ],
                difficulty=2,
                domain_tags=["Python", "算法", "链表"]
            ),
            EvaluationTask(
                task_id="cg_009",
                task_type=TaskType.CODE_GENERATION,
                name="最大子数组和",
                description="求解最大子数组和",
                requirement="给定整数数组，找到连续子数组的最大和",
                test_cases=[
                    {"input": [-2,1,-3,4,-1,2,1,-5,4], "expected": 6},
                    {"input": [1], "expected": 1},
                    {"input": [5,4,-1,7,8], "expected": 23}
                ],
                difficulty=3,
                domain_tags=["Python", "算法", "动态规划"]
            ),
            EvaluationTask(
                task_id="cg_010",
                task_type=TaskType.CODE_GENERATION,
                name="有效的括号",
                description="判断括号字符串是否有效",
                requirement="判断给定字符串中的括号是否匹配有效：()[]{}",
                test_cases=[
                    {"input": "()", "expected": True},
                    {"input": "()[]{}", "expected": True},
                    {"input": "(]", "expected": False}
                ],
                difficulty=2,
                domain_tags=["Python", "栈"]
            ),
            EvaluationTask(
                task_id="cg_011",
                task_type=TaskType.CODE_GENERATION,
                name="删除排序数组中的重复项",
                description="删除有序数组中的重复项",
                requirement="原地删除有序数组中的重复项，返回新长度",
                test_cases=[
                    {"input": [1,1,2], "expected": 2},
                    {"input": [0,0,1,1,1,2,2,3,3,4], "expected": 5}
                ],
                difficulty=2,
                domain_tags=["Python", "数组", "双指针"]
            ),
            EvaluationTask(
                task_id="cg_012",
                task_type=TaskType.CODE_GENERATION,
                name="爬楼梯",
                description="爬楼梯问题",
                requirement="有n阶楼梯，每次可爬1或2阶，求爬到顶的不同方法数",
                test_cases=[
                    {"input": 2, "expected": 2},
                    {"input": 3, "expected": 3},
                    {"input": 4, "expected": 5}
                ],
                difficulty=2,
                domain_tags=["Python", "动态规划"]
            ),
            EvaluationTask(
                task_id="cg_013",
                task_type=TaskType.CODE_GENERATION,
                name="反转整数",
                description="反转整数数字",
                requirement="反转整数数字，超出32位整数范围返回0",
                test_cases=[
                    {"input": 123, "expected": 321},
                    {"input": -123, "expected": -321},
                    {"input": 120, "expected": 21}
                ],
                difficulty=2,
                domain_tags=["Python", "数学"]
            ),
            EvaluationTask(
                task_id="cg_014",
                task_type=TaskType.CODE_GENERATION,
                name="实现strStr",
                description="字符串匹配查找子串",
                requirement="实现strStr函数，返回子串首次出现位置，不存在返回-1",
                test_cases=[
                    {"input": ("hello", "ll"), "expected": 2},
                    {"input": ("aaaaa", "bba"), "expected": -1}
                ],
                difficulty=2,
                domain_tags=["Python", "字符串", "匹配"]
            ),
            EvaluationTask(
                task_id="cg_015",
                task_type=TaskType.CODE_GENERATION,
                name="移除元素",
                description="原地移除指定元素",
                requirement="原地移除数组中等于val的元素，返回新长度",
                test_cases=[
                    {"input": ([3,2,2,3], 3), "expected": 2},
                    {"input": ([0,1,2,2,0,2,2], 2), "expected": 3}
                ],
                difficulty=2,
                domain_tags=["Python", "数组"]
            ),
            EvaluationTask(
                task_id="cg_016",
                task_type=TaskType.CODE_GENERATION,
                name="搜索插入位置",
                description="搜索插入位置",
                requirement="在有序数组中查找目标值，返回索引或插入位置",
                test_cases=[
                    {"input": ([1,3,5,6], 5), "expected": 2},
                    {"input": ([1,3,5,6], 2), "expected": 1}
                ],
                difficulty=2,
                domain_tags=["Python", "查找", "二分"]
            ),
            EvaluationTask(
                task_id="cg_017",
                task_type=TaskType.CODE_GENERATION,
                name="求众数",
                description="求数组中出现次数超过n/2的元素",
                requirement="求数组中出现次数超过数组长度一半的元素",
                test_cases=[
                    {"input": [3,2,3], "expected": 3},
                    {"input": [2,2,1,1,1,2,2], "expected": 2}
                ],
                difficulty=2,
                domain_tags=["Python", "数组"]
            ),
            EvaluationTask(
                task_id="cg_018",
                task_type=TaskType.CODE_GENERATION,
                name="盛最多水的容器",
                description="双指针求最大容器",
                requirement="给定高度数组，求能容纳最多水的两条柱子",
                test_cases=[
                    {"input": [1,8,6,2,5,4,8,3,7], "expected": 49},
                    {"input": [1,1], "expected": 1}
                ],
                difficulty=3,
                domain_tags=["Python", "双指针"]
            ),
            EvaluationTask(
                task_id="cg_019",
                task_type=TaskType.CODE_GENERATION,
                name="罗马数字转整数",
                description="罗马数字转换为整数",
                requirement="将罗马数字转换为整数（I=1, V=5, X=10等）",
                test_cases=[
                    {"input": "III", "expected": 3},
                    {"input": "IV", "expected": 4},
                    {"input": "IX", "expected": 9}
                ],
                difficulty=2,
                domain_tags=["Python", "字符串"]
            ),
            EvaluationTask(
                task_id="cg_020",
                task_type=TaskType.CODE_GENERATION,
                name="最长公共前缀",
                description="求字符串数组的最长公共前缀",
                requirement="查找字符串数组中的最长公共前缀",
                test_cases=[
                    {"input": ["flower","flow","flight"], "expected": "fl"},
                    {"input": ["dog","racecar","car"], "expected": ""}
                ],
                difficulty=1,
                domain_tags=["Python", "字符串"]
            ),
            EvaluationTask(
                task_id="cg_021",
                task_type=TaskType.CODE_GENERATION,
                name="验证二叉搜索树",
                description="验证是否为合法二叉搜索树",
                requirement="验证给定的二叉树是否为有效的二叉搜索树",
                test_cases=[
                    {"input": [2,1,3], "expected": True},
                    {"input": [5,1,4,None,None,3,6], "expected": False}
                ],
                difficulty=3,
                domain_tags=["Python", "树", "递归"]
            ),
            EvaluationTask(
                task_id="cg_022",
                task_type=TaskType.CODE_GENERATION,
                name="对称二叉树",
                description="判断二叉树是否对称",
                requirement="判断给定的二叉树是否轴对称",
                test_cases=[
                    {"input": [1,2,2,3,4,4,3], "expected": True},
                    {"input": [1,2,2,None,3,None,3], "expected": False}
                ],
                difficulty=2,
                domain_tags=["Python", "树"]
            ),
            EvaluationTask(
                task_id="cg_023",
                task_type=TaskType.CODE_GENERATION,
                name="层序遍历二叉树",
                description="二叉树的层序遍历",
                requirement="实现二叉树的层序遍历，按层返回节点值",
                test_cases=[
                    {"input": [3,9,20,None,None,15,7], "expected": [[3],[9,20],[15,7]]}
                ],
                difficulty=2,
                domain_tags=["Python", "树", "BFS"]
            ),
            EvaluationTask(
                task_id="cg_024",
                task_type=TaskType.CODE_GENERATION,
                name="实现LRU缓存",
                description="实现最近最少使用缓存",
                requirement="设计并实现LRU缓存数据结构",
                test_cases=[
                    {"input": (2, ["put",1,1,"put",2,2,"get",1,"get",2]), "expected": [None,None,None,1,2]}
                ],
                difficulty=4,
                domain_tags=["Python", "设计", "缓存"]
            ),
            EvaluationTask(
                task_id="cg_025",
                task_type=TaskType.CODE_GENERATION,
                name="堆排序",
                description="实现堆排序算法",
                requirement="实现堆排序算法对数组进行升序排序",
                test_cases=[
                    {"input": [5,2,8,1,9,3], "expected": [1,2,3,5,8,9]}
                ],
                difficulty=3,
                domain_tags=["Python", "排序", "堆"]
            ),
        ]
        
        for task in code_gen_tasks:
            self.add_task(task)
        
        # ==================== Bug修复任务 (20+) ====================
        bug_fix_tasks = [
            EvaluationTask(
                task_id="bf_001",
                task_type=TaskType.BUG_FIX,
                name="修复排序函数bug",
                description="修复冒泡排序函数中的边界问题",
                requirement="以下冒泡排序函数在处理空列表时会报错，请修复：\ndef bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(n-i-1):\n            if arr[j] > arr[j+1]:\n                arr[j], arr[j+1] = arr[j+1], arr[j]\n    return arr",
                test_cases=[
                    {"input": [], "expected": []},
                    {"input": [3,1,2], "expected": [1,2,3]}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "排序"]
            ),
            EvaluationTask(
                task_id="bf_002",
                task_type=TaskType.BUG_FIX,
                name="修复空指针异常",
                description="修复空列表访问导致的IndexError",
                requirement="修复以下函数处理空列表时的IndexError：\ndef get_first_element(lst):\n    return lst[0]",
                test_cases=[
                    {"input": [], "expected": None},
                    {"input": [1,2,3], "expected": 1}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "异常处理"]
            ),
            EvaluationTask(
                task_id="bf_003",
                task_type=TaskType.BUG_FIX,
                name="修复除零错误",
                description="修复除法函数中的除零错误",
                requirement="修复以下函数处理除数为0的情况：\ndef divide(a, b):\n    return a / b",
                test_cases=[
                    {"input": (10, 2), "expected": 5},
                    {"input": (10, 0), "expected": None}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "异常处理"]
            ),
            EvaluationTask(
                task_id="bf_004",
                task_type=TaskType.BUG_FIX,
                name="修复字符串拼接错误",
                description="修复字符串拼接时类型错误",
                requirement="修复以下函数在拼接数字时的类型错误：\ndef concat(a, b):\n    return a + b",
                test_cases=[
                    {"input": ("hello", "world"), "expected": "helloworld"},
                    {"input": (1, 2), "expected": "12"}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "类型转换"]
            ),
            EvaluationTask(
                task_id="bf_005",
                task_type=TaskType.BUG_FIX,
                name="修复循环索引错误",
                description="修复循环中的索引越界问题",
                requirement="修复以下函数遍历列表时的越界问题：\ndef find_max(lst):\n    max_val = lst[0]\n    for i in range(1, len(lst)+1):\n        if lst[i] > max_val:\n            max_val = lst[i]\n    return max_val",
                test_cases=[
                    {"input": [1,5,3], "expected": 5},
                    {"input": [1], "expected": 1}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "索引"]
            ),
            EvaluationTask(
                task_id="bf_006",
                task_type=TaskType.BUG_FIX,
                name="修复字典键不存在错误",
                description="修复访问不存在的字典键",
                requirement="修复以下函数处理不存在的键：\ndef get_value(d, key):\n    return d[key]",
                test_cases=[
                    {"input": ({"a": 1}, "a"), "expected": 1},
                    {"input": ({"a": 1}, "b"), "expected": None}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "字典"]
            ),
            EvaluationTask(
                task_id="bf_007",
                task_type=TaskType.BUG_FIX,
                name="修复递归深度错误",
                description="修复递归函数的最大递归深度问题",
                requirement="修复以下递归函数处理大数时的栈溢出：\ndef fib(n):\n    return fib(n-1) + fib(n-2) if n > 1 else n",
                test_cases=[
                    {"input": 10, "expected": 55},
                    {"input": 0, "expected": 0}
                ],
                difficulty=3,
                domain_tags=["Python", "bug修复", "递归", "动态规划"]
            ),
            EvaluationTask(
                task_id="bf_008",
                task_type=TaskType.BUG_FIX,
                name="修复浮点数精度问题",
                description="修复浮点数比较精度问题",
                requirement="修复以下函数处理浮点数比较：\ndef is_equal(a, b):\n    return a == b",
                test_cases=[
                    {"input": (0.1+0.2, 0.3), "expected": True}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "浮点数"]
            ),
            EvaluationTask(
                task_id="bf_009",
                task_type=TaskType.BUG_FIX,
                name="修复文件关闭问题",
                description="修复文件未关闭的资源泄漏",
                requirement="修复以下函数确保文件正确关闭：\ndef read_file(filename):\n    f = open(filename, 'r')\n    return f.read()",
                test_cases=[],
                difficulty=2,
                domain_tags=["Python", "bug修复", "文件IO"]
            ),
            EvaluationTask(
                task_id="bf_010",
                task_type=TaskType.BUG_FIX,
                name="修复深拷贝问题",
                description="修复浅拷贝导致的引用问题",
                requirement="修复以下函数确保返回独立副本：\ndef duplicate_list(lst):\n    return lst[:]",
                test_cases=[
                    {"input": [[1,2], [3,4]], "expected": [[1,2], [3,4]]}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "拷贝"]
            ),
            EvaluationTask(
                task_id="bf_011",
                task_type=TaskType.BUG_FIX,
                name="修复默认参数可变对象bug",
                description="修复可变默认参数导致的共享状态问题",
                requirement="修复以下函数的默认参数问题：\ndef append_to(element, to=[]):\n    to.append(element)\n    return to",
                test_cases=[
                    {"input": (1,), "expected": [1]},
                    {"input": (2,), "expected": [2]}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "默认参数"]
            ),
            EvaluationTask(
                task_id="bf_012",
                task_type=TaskType.BUG_FIX,
                name="修复条件判断逻辑错误",
                description="修复条件判断中的逻辑错误",
                requirement="修复以下函数中判断偶数的错误逻辑：\ndef is_even(n):\n    return n % 2 == 1",
                test_cases=[
                    {"input": 4, "expected": True},
                    {"input": 3, "expected": False}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "逻辑"]
            ),
            EvaluationTask(
                task_id="bf_013",
                task_type=TaskType.BUG_FIX,
                name="修复字符串大小写敏感问题",
                description="修复大小写不敏感比较问题",
                requirement="修复以下函数实现大小写不敏感比较：\ndef is_same_case(a, b):\n    return a == b",
                test_cases=[
                    {"input": ("Hello", "hello"), "expected": True},
                    {"input": ("Hello", "HELLO"), "expected": True}
                ],
                difficulty=1,
                domain_tags=["Python", "bug修复", "字符串"]
            ),
            EvaluationTask(
                task_id="bf_014",
                task_type=TaskType.BUG_FIX,
                name="修复列表推导式变量泄漏",
                description="修复列表推导式中的变量作用域问题",
                requirement="修复以下代码确保i在循环后不变：\ni = 0\nresult = [i for i in range(5)]\nreturn i",
                test_cases=[
                    {"input": None, "expected": 0}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "作用域"]
            ),
            EvaluationTask(
                task_id="bf_015",
                task_type=TaskType.BUG_FIX,
                name="修复正则表达式匹配错误",
                description="修复正则表达式匹配模式错误",
                requirement="修复以下函数正确匹配邮箱格式：\ndef validate_email(email):\n    import re\n    return re.match(r'\\w+@\\w+.\\w', email) is not None",
                test_cases=[
                    {"input": "test@example.com", "expected": True},
                    {"input": "invalid@", "expected": False}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "正则"]
            ),
            EvaluationTask(
                task_id="bf_016",
                task_type=TaskType.BUG_FIX,
                name="修复日期解析错误",
                description="修复日期字符串解析格式错误",
                requirement="修复以下函数正确解析日期：\ndef parse_date(s):\n    from datetime import datetime\n    return datetime.strptime(s, '%Y-%m-%d')",
                test_cases=[
                    {"input": "2024-01-01", "expected": "2024-01-01"}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "日期"]
            ),
            EvaluationTask(
                task_id="bf_017",
                task_type=TaskType.BUG_FIX,
                name="修复JSON解析错误",
                description="修复JSON解析异常处理",
                requirement="修复以下函数处理无效JSON：\ndef parse_json(s):\n    import json\n    return json.loads(s)",
                test_cases=[
                    {"input": '{"a": 1}', "expected": {"a": 1}},
                    {"input": "invalid", "expected": None}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "JSON"]
            ),
            EvaluationTask(
                task_id="bf_018",
                task_type=TaskType.BUG_FIX,
                name="修复多线程共享变量问题",
                description="修复多线程中的竞态条件",
                requirement="修复以下函数处理线程安全问题：\ncounter = 0\ndef increment():\n    global counter\n    counter += 1",
                test_cases=[],
                difficulty=3,
                domain_tags=["Python", "bug修复", "多线程"]
            ),
            EvaluationTask(
                task_id="bf_019",
                task_type=TaskType.BUG_FIX,
                name="修复生成器迭代错误",
                description="修复生成器重迭代问题",
                requirement="修复以下函数使其可重复迭代：\ndef generate_numbers(n):\n    for i in range(n):\n        yield i",
                test_cases=[],
                difficulty=2,
                domain_tags=["Python", "bug修复", "生成器"]
            ),
            EvaluationTask(
                task_id="bf_020",
                task_type=TaskType.BUG_FIX,
                name="修复装饰器顺序问题",
                description="修复装饰器执行顺序",
                requirement="修复以下装饰器确保执行顺序正确：\n@decorator1\n@decorator2\ndef func():\n    pass",
                test_cases=[],
                difficulty=3,
                domain_tags=["Python", "bug修复", "装饰器"]
            ),
            EvaluationTask(
                task_id="bf_021",
                task_type=TaskType.BUG_FIX,
                name="修复迭代器耗尽问题",
                description="修复迭代器一次性消耗问题",
                requirement="修复以下函数确保可重复消费：\ndef get_iterator(lst):\n    return iter(lst)",
                test_cases=[],
                difficulty=2,
                domain_tags=["Python", "bug修复", "迭代器"]
            ),
            EvaluationTask(
                task_id="bf_022",
                task_type=TaskType.BUG_FIX,
                name="修复HTTP请求超时处理",
                description="修复HTTP请求超时异常",
                requirement="修复以下函数处理请求超时：\nimport requests\ndef fetch(url):\n    return requests.get(url).json()",
                test_cases=[],
                difficulty=2,
                domain_tags=["Python", "bug修复", "HTTP"]
            ),
            EvaluationTask(
                task_id="bf_023",
                task_type=TaskType.BUG_FIX,
                name="修复数据库连接泄漏",
                description="修复数据库连接未关闭问题",
                requirement="修复以下函数确保连接正确关闭：\ndef query_db(sql):\n    conn = get_connection()\n    return conn.execute(sql)",
                test_cases=[],
                difficulty=3,
                domain_tags=["Python", "bug修复", "数据库"]
            ),
            EvaluationTask(
                task_id="bf_024",
                task_type=TaskType.BUG_FIX,
                name="修复函数参数传递错误",
                description="修复可变对象参数被意外修改",
                requirement="修复以下函数不修改原列表：\ndef sort_list(lst):\n    lst.sort()\n    return lst",
                test_cases=[
                    {"input": [3,1,2], "expected": [1,2,3]}
                ],
                difficulty=2,
                domain_tags=["Python", "bug修复", "参数"]
            ),
        ]
        
        for task in bug_fix_tasks:
            self.add_task(task)
        
        # ==================== 需求分解任务 (20+) ====================
        req_decomp_tasks = [
            EvaluationTask(
                task_id="rd_001",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="待办清单应用分解",
                description="分解待办清单应用的开发需求",
                requirement="开发一个Web版待办清单应用，支持用户注册登录、添加/删除/修改待办、标记完成、分类管理功能，使用Python Flask后端和React前端",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "Web开发"]
            ),
            EvaluationTask(
                task_id="rd_002",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="在线商城系统分解",
                description="分解在线商城系统开发需求",
                requirement="开发一个在线商城系统，包含用户管理、商品展示、购物车、订单处理、支付集成、库存管理功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "电商"]
            ),
            EvaluationTask(
                task_id="rd_003",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="社交媒体App分解",
                description="分解社交媒体应用开发需求",
                requirement="开发一个社交媒体App，支持用户资料、发帖、点赞、评论、关注、私信、话题标签、推荐算法功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "社交"]
            ),
            EvaluationTask(
                task_id="rd_004",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="博客系统分解",
                description="分解博客系统开发需求",
                requirement="开发一个博客平台，支持文章撰写、分类标签、评论系统、搜索功能、用户关注、内容推荐、后台管理",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "内容管理"]
            ),
            EvaluationTask(
                task_id="rd_005",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="在线教育平台分解",
                description="分解在线教育平台开发需求",
                requirement="开发一个在线教育平台，包含课程管理、视频播放、作业提交、在线考试、学习进度跟踪、证书颁发、讨论区功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "教育"]
            ),
            EvaluationTask(
                task_id="rd_006",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="企业内部系统分解",
                description="分解企业内部管理系统开发需求",
                requirement="开发一个企业内部管理系统，包含员工管理、考勤打卡、审批流程、公告发布、文件共享、即时通讯功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "企业软件"]
            ),
            EvaluationTask(
                task_id="rd_007",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="智能家居系统分解",
                description="分解智能家居系统开发需求",
                requirement="开发一个智能家居控制系统，支持设备配网、远程控制、定时任务、场景联动、能耗统计、语音控制功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "物联网"]
            ),
            EvaluationTask(
                task_id="rd_008",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="外卖配送平台分解",
                description="分解外卖配送平台开发需求",
                requirement="开发一个外卖配送平台，包含商家入驻、菜品管理、订单处理、骑手调度、实时追踪、评价系统、优惠券功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "O2O"]
            ),
            EvaluationTask(
                task_id="rd_009",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="在线医疗系统分解",
                description="分解在线医疗系统开发需求",
                requirement="开发一个在线医疗平台，包含预约挂号、在线问诊、电子处方、药品配送、健康档案、医疗科普功能",
                test_cases=[],
                difficulty=5,
                domain_tags=["需求分析", "医疗"]
            ),
            EvaluationTask(
                task_id="rd_010",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="旅游预订平台分解",
                description="分解旅游预订平台开发需求",
                requirement="开发一个旅游预订平台，包含景点介绍、酒店预订、机票购买、行程规划、用户评价、攻略分享功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "旅游"]
            ),
            EvaluationTask(
                task_id="rd_011",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="金融理财App分解",
                description="分解金融理财应用开发需求",
                requirement="开发一个金融理财App，包含账户管理、投资理财、基金购买、收益分析、风险评估、交易记录功能",
                test_cases=[],
                difficulty=5,
                domain_tags=["需求分析", "金融"]
            ),
            EvaluationTask(
                task_id="rd_012",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="招聘平台分解",
                description="分解招聘平台开发需求",
                requirement="开发一个招聘平台，包含职位发布、简历投递、智能推荐、在线面试、企业评价、薪资分析功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "人力资源"]
            ),
            EvaluationTask(
                task_id="rd_013",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="餐饮管理系统分解",
                description="分解餐饮管理系统开发需求",
                requirement="开发一个餐饮管理系统，包含菜品管理、订单处理、桌位管理、会员系统、财务统计、员工管理功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "餐饮"]
            ),
            EvaluationTask(
                task_id="rd_014",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="智慧校园平台分解",
                description="分解智慧校园平台开发需求",
                requirement="开发一个智慧校园平台，包含教务管理、成绩查询、图书借阅、宿舍管理、校园卡消费、通知公告功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "教育"]
            ),
            EvaluationTask(
                task_id="rd_015",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="视频流媒体平台分解",
                description="分解视频流媒体平台开发需求",
                requirement="开发一个视频流媒体平台，包含视频上传、转码处理、播放管理、弹幕系统、推荐算法、用户会员功能",
                test_cases=[],
                difficulty=5,
                domain_tags=["需求分析", "流媒体"]
            ),
            EvaluationTask(
                task_id="rd_016",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="CRM客户管理系统分解",
                description="分解CRM系统开发需求",
                requirement="开发一个CRM系统，包含客户管理、销售跟进、合同管理、数据分析、营销自动化、报表生成功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "企业软件"]
            ),
            EvaluationTask(
                task_id="rd_017",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="共享单车系统分解",
                description="分解共享单车系统开发需求",
                requirement="开发一个共享单车平台，包含扫码开锁、计费规则、站点管理、车辆调度、故障报修、用户投诉功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "共享经济"]
            ),
            EvaluationTask(
                task_id="rd_018",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="知识库系统分解",
                description="分解知识库系统开发需求",
                requirement="开发一个企业知识库系统，包含文档管理、版本控制、权限管理、全文搜索、标签分类、评论协作功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "知识管理"]
            ),
            EvaluationTask(
                task_id="rd_019",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="区块链交易平台分解",
                description="分解区块链交易平台开发需求",
                requirement="开发一个区块链交易平台，包含钱包管理、交易下单、市场行情、风控系统、链上追踪、KYC认证功能",
                test_cases=[],
                difficulty=5,
                domain_tags=["需求分析", "区块链"]
            ),
            EvaluationTask(
                task_id="rd_020",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="游戏平台分解",
                description="分解游戏平台开发需求",
                requirement="开发一个游戏平台，包含游戏展示、账号管理、支付充值、排行榜、社交分享、客服支持功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "游戏"]
            ),
            EvaluationTask(
                task_id="rd_021",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="物业管理系统分解",
                description="分解物业管理系统开发需求",
                requirement="开发一个物业管理系统，包含住户管理、费用收缴、维修工单、访客登记、公告通知、设备巡检功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "物业"]
            ),
            EvaluationTask(
                task_id="rd_022",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="数据分析平台分解",
                description="分解数据分析平台开发需求",
                requirement="开发一个数据分析平台，包含数据接入、可视化报表、自定义查询、仪表盘、告警通知、权限管理功能",
                test_cases=[],
                difficulty=4,
                domain_tags=["需求分析", "数据分析"]
            ),
            EvaluationTask(
                task_id="rd_023",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="短链接服务分解",
                description="分解短链接服务开发需求",
                requirement="开发一个短链接服务，包含链接生成、访问统计、链接管理、自定义别名、批量创建、API接口功能",
                test_cases=[],
                difficulty=2,
                domain_tags=["需求分析", "工具服务"]
            ),
            EvaluationTask(
                task_id="rd_024",
                task_type=TaskType.REQUIREMENT_DECOMPOSITION,
                name="邮件营销平台分解",
                description="分解邮件营销平台开发需求",
                requirement="开发一个邮件营销平台，包含邮件模板、发送计划、联系人管理、发送统计、打开率分析、退订管理功能",
                test_cases=[],
                difficulty=3,
                domain_tags=["需求分析", "营销"]
            ),
        ]
        
        for task in req_decomp_tasks:
            self.add_task(task)
    
    def export_to_json(self, file_path: str) -> None:
        """导出数据集到JSON文件"""
        data = []
        for task in self.tasks.values():
            task_dict = {
                "task_id": task.task_id,
                "task_type": task.task_type.value,
                "name": task.name,
                "description": task.description,
                "requirement": task.requirement,
                "test_cases": task.test_cases,
                "expected_output": task.expected_output,
                "difficulty": task.difficulty,
                "domain_tags": task.domain_tags or [],
                "metadata": task.metadata or {}
            }
            data.append(task_dict)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_json(cls, file_path: str) -> "TaskDataset":
        """从JSON文件加载数据集"""
        dataset = cls()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 兼容两种格式：
        # 1) 旧格式：[{...}, {...}]
        # 2) 扩展格式：{"tasks": [{...}, {...}], ...}
        if isinstance(data, dict):
            data = data.get("tasks", [])
        if not isinstance(data, list):
            raise ValueError("数据集JSON格式不正确：应为任务列表或包含tasks字段的对象")
        
        for task_dict in data:
            raw_type = task_dict.get("task_type", TaskType.CODE_GENERATION.value)
            try:
                task_type = TaskType(raw_type)
            except ValueError:
                # 兼容扩展任务类型，回退为代码生成以保证评测流程可运行。
                task_type = TaskType.CODE_GENERATION

            description = task_dict.get("description") or task_dict.get("requirement", "")
            task = EvaluationTask(
                task_id=task_dict["task_id"],
                task_type=task_type,
                name=task_dict["name"],
                description=description,
                requirement=task_dict["requirement"],
                test_cases=task_dict.get("test_cases", []),
                expected_output=task_dict.get("expected_output"),
                difficulty=task_dict.get("difficulty", 3),
                domain_tags=task_dict.get("domain_tags", []),
                metadata=task_dict.get("metadata", {})
            )
            dataset.add_task(task)
        
        return dataset
