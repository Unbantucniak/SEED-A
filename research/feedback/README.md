# 经验如何随开发反馈改变

一条经验可以描述库提供的一个选项，但该选项未必适合当下任务。下面的两个例子分别用测试失败调整下一次推荐，以及用一条历史观测纠正命名转换结果。

## 运行开发反馈演示

在本目录使用 Python 3.11 或更高版本。建议在自己的虚拟环境里运行以下命令。

```console
python -m pip install pytest==9.0.3
python tools/demo_experience_feedback.py
```

演示下载并核对 [case-converter 1.2.0](https://github.com/chrisdoherty4/python-case-converter/tree/v1.2.0)，在临时项目内创建两个遵循默认行为的适配函数。上游的一个测试表明显式设置 `strip_punctuation=False` 可以保留标点。开发者记录了这个选项，再用同一上游项目的 camelcase、pascalcase 测试分别验收默认适配函数。脚本事先写好采用和跳过两种动作，运行时由反馈策略选择，无需模型调用。

| 验收任务 | 策略 | 实际选择 | 通过的测试 |
| --- | --- | --- | --- |
| CamelCase 适配函数 | 学习策略，尚无历史 | 采用经验，显式保留标点 | 9/11 |
| PascalCase 适配函数 | 固定策略 | 采用经验，显式保留标点 | 10/12 |
| 同一个 PascalCase 适配函数 | 学习策略，已有 CamelCase 失败反馈 | 跳过经验，调用上游默认选项 | 12/12 |

两条 PascalCase 记录使用相同的测试。固定策略的回执不参与学习，学习策略依据第一行的验收结果改变选择。脚本会输出本机生成的 JSON 路径，里面有每次决策、动作和具体测试项。

## 回放一条历史观测

```console
python replay_heldout.py
```

默认读取本目录的 `example.json`。这是专为解释方法编写的教学输入，包含两个示例草稿、两次历史观测及一条基础测试。脚本在上游库上实际运行目标输入取得参考值。固定规则将 `openURLFile` 转成 `OPEN_URL_FILE`，上游结果为 `OPEN_U_R_L_FILE`。先前的 `readXMLHeader` 观测表明该版本会拆开连续大写字母。学习策略据此选中正确草稿。临时撤回这条观测后，固定规则的错误随之重现。另一个含数字的目标由规则给出正确结果。该例用于说明选择过程，不计入研究实验成绩。

两个命令都接受 `--archive <ZIP路径>`，可使用预先取得的上游 v1.2.0 源码归档离线运行。程序核对归档的 SHA-256 摘要 `4efefbb0e0e1cb53e492b16bfcadc677598527e88cb9a7a0c8300b9013c4098f`。持有学校交付包的读者可再给回放命令传 `--evidence <已封存的案例.json路径>`，验证包中原有案例。回放命令只依赖 Python 标准库和已校验的源码归档。开发反馈演示需要 pytest。

## 在自己的项目里使用

准备一份 UTF-8 文本，写下经验内容和可追溯的来源。以下 PowerShell 示例中，将路径、版本、任务族、任务描述及测试目标换成自己的值。

```powershell
$scopeArgs = @('--repo', 'D:/work/example', '--version', 'v1', '--family', '导出接口')
$dbArgs = @('--db', "$env:LOCALAPPDATA/SEED-A/feedback-review.sqlite3")
$cli = 'tools/experience_feedback.py'
$card = python $cli @dbArgs remember @scopeArgs --file 'D:/notes/export.md' | ConvertFrom-Json
$trial = python $cli @dbArgs decide @scopeArgs --task '实现订单导出接口' --card $card.card --policy learn --prior use | ConvertFrom-Json
$trial | ConvertTo-Json -Depth 6
```

开发者或研发模型完成这次任务后，记录实际动作。以下命令对应实际采用经验的情形。实际跳过时填写 `--actual skip`。如果测试依赖项目专属环境，可用 `--python` 指定其中的 Python 可执行文件。

```powershell
python $cli @dbArgs verify @scopeArgs --id $trial.id --actual use --target 'tests/test_export.py'
python $cli @dbArgs show @scopeArgs --id $trial.id
```

通过返回 0，断言失败返回 1，两者都会写入反馈。收集失败、全部跳过或超时返回 2，原决策保留待验收状态。下一项任务再次运行 `decide` 时，命令读取同一项目目录、版本、任务族与经验编号下已完成的学习模式回执。用 `--policy fixed` 可保留相同初始偏好的对照。SQLite 数据库和演示生成的 JSON 均在本机，会记录本机路径。

在本目录运行 `python -m pytest -q tests` 可核查作用域隔离、反馈重放、动作变更、无效验收和重复回执等行为。

