import * as vscode from 'vscode';
import axios from 'axios';

let apiEndpoint = vscode.workspace.getConfiguration('self-evolution-agent').get<string>('apiEndpoint', 'http://localhost:8000');
let autoSave = vscode.workspace.getConfiguration('self-evolution-agent').get<boolean>('autoSaveExperience', true);

export function activate(context: vscode.ExtensionContext) {
	console.log('自学习自演化智能助手插件已激活');

	// 监听配置变更
	vscode.workspace.onDidChangeConfiguration(e => {
		if (e.affectsConfiguration('self-evolution-agent.apiEndpoint')) {
			apiEndpoint = vscode.workspace.getConfiguration('self-evolution-agent').get<string>('apiEndpoint', 'http://localhost:8000');
		}
		if (e.affectsConfiguration('self-evolution-agent.autoSaveExperience')) {
			autoSave = vscode.workspace.getConfiguration('self-evolution-agent').get<boolean>('autoSaveExperience', true);
		}
	});

	// 注册命令：搜索相关经验
	let searchCommand = vscode.commands.registerCommand('self-evolution-agent.searchExperience', async () => {
		const query = await vscode.window.showInputBox({
			prompt: '输入搜索关键词，查找相关开发经验',
			placeHolder: '例如：Python快速排序实现'
		});
		if (!query) { return; }

		try {
			const response = await axios.post(`${apiEndpoint}/api/experience/search`, { query });
			const experiences = response.data;
			
			if (experiences.length === 0) {
				vscode.window.showInformationMessage('未找到相关经验');
				return;
			}

			// 展示搜索结果
			const items = experiences.map((exp: any) => ({
				label: `${exp.task_intent.task_type}: ${exp.task_intent.original_requirement.substring(0, 50)}`,
				description: `成功率: ${(exp.dynamic_meta.success_rate * 100).toFixed(1)}% | 使用次数: ${exp.dynamic_meta.use_count}`,
				detail: exp.execution_result.final_output.substring(0, 200),
				experience: exp
			}));

			const selected = await vscode.window.showQuickPick(items, {
				placeHolder: '选择要查看的经验',
				matchOnDescription: true,
				matchOnDetail: true
			});

			if (selected) {
				// 打开经验详情
				const doc = await vscode.workspace.openTextDocument({
					content: `# 经验详情\n\n` +
						`## 任务信息\n` +
						`- 类型: ${selected.experience.task_intent.task_type}\n` +
						`- 需求: ${selected.experience.task_intent.original_requirement}\n` +
						`- 用户指令: ${selected.experience.task_intent.user_instruction}\n\n` +
						`## 执行结果\n` +
						`- 状态: ${selected.experience.execution_result.is_success ? '✅ 成功' : '❌ 失败'}\n` +
						`- 执行耗时: ${selected.experience.execution_result.execution_time}s\n\n` +
						`## 最终输出\n\`\`\`\n${selected.experience.execution_result.final_output}\n\`\`\`\n\n` +
						`## 元属性\n` +
						`- 成功率: ${(selected.experience.dynamic_meta.success_rate * 100).toFixed(1)}%\n` +
						`- 使用次数: ${selected.experience.dynamic_meta.use_count}\n` +
						`- 时效性: ${(selected.experience.dynamic_meta.timeliness * 100).toFixed(1)}%\n` +
						`- 通用性: ${(selected.experience.static_meta.generalization * 100).toFixed(1)}%`,
					language: 'markdown'
				});
				await vscode.window.showTextDocument(doc);
			}
		} catch (error) {
			vscode.window.showErrorMessage(`搜索经验失败: ${(error as Error).message}`);
		}
	});

	// 注册命令：保存当前经验
	let saveCommand = vscode.commands.registerCommand('self-evolution-agent.saveCurrentExperience', async () => {
		const editor = vscode.window.activeTextEditor;
		if (!editor) {
			vscode.window.showErrorMessage('没有打开的文本编辑器');
			return;
		}

		const requirement = await vscode.window.showInputBox({
			prompt: '输入该经验对应的需求描述',
			placeHolder: '例如：实现快速排序函数'
		});
		if (!requirement) { return; }

		const code = editor.document.getText(editor.selection) || editor.document.getText();
		
		try {
			await axios.post(`${apiEndpoint}/api/experience/add`, {
				original_requirement: requirement,
				user_instruction: requirement,
				task_type: '代码生成',
				final_output: code,
				is_success: true,
				execution_time: 1.0,
				source_credibility: 1.0
			});
			vscode.window.showInformationMessage('经验保存成功！');
		} catch (error) {
			vscode.window.showErrorMessage(`保存经验失败: ${(error as Error).message}`);
		}
	});

	// 注册命令：打开经验库面板
	let showLibraryCommand = vscode.commands.registerCommand('self-evolution-agent.showExperienceLibrary', () => {
		vscode.commands.executeCommand('workbench.view.extension.self-evolution-agent');
	});

	context.subscriptions.push(searchCommand, saveCommand, showLibraryCommand);
}

export function deactivate() {
	console.log('自学习自演化智能助手插件已停用');
}
