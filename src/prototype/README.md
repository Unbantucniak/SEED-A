# SEED-A 经验助手

VS Code 扩展让开发者选中 Python 代码、用项目的 pytest 验证并保存经验，随后在同一项目和版本中检索、预览差异、采纳或撤销。重新运行测试会将结果关联到所用的经验。插件版本为 0.3.2，要求 VS Code 1.85 或更新版本。

下载安装包、启动本机服务和运行自带示例见[0.3.2 安装与试用](https://github.com/Unbantucniak/SEED-A/tree/main/releases/ide-0.3.2)。

## 从源码构建

在本目录中使用带 npm 的 Node.js 22 或更新版本执行以下命令。首次安装开发依赖需要网络。

```powershell
npm ci
npm run check
npm run test:workbench
npm run package
```

生成的 VSIX 在 `dist/`。三个测试脚本分别覆盖工作台 HTTP 与命令处理、代码替换与撤销的选区范围，以及空搜索后浏览与预览。测试通过 VS Code API 替身运行。正式分发的安装包及其 SHA-256 见安装说明。

## 配置项目与版本

默认从项目文件夹与当前 Git 分支生成检索范围，非 Git 项目使用 `v1`。多个克隆如需共享经验，可设置相同的 `seeda.memoryScope` 与 `seeda.memoryVersion`。测试解释器由 `seeda.pythonPath` 指定。经验服务默认为 `http://127.0.0.1:8765`，仅接受本机地址。草稿和测试结果保存在运行服务的计算机上。
