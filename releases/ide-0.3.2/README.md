# SEED-A 0.3.2 安装与试用

这个目录包含正式插件安装包、轻量本机经验服务和一个带测试的 Python 项目。轻量服务提供检索、版本筛选、草稿和测试结果记录，使用词项匹配，不需要模型或 API 密钥。以下步骤适用于 Windows x64。

## 安装与连接

1. 下载并解压发行页的 SEED-A-IDE-0.3.2.zip，或克隆本仓库。在解压目录或仓库根目录打开 PowerShell，使用 Python 3.13 创建虚拟环境。首次安装依赖需要访问 Python 包源。

   ```powershell
   cd releases/ide-0.3.2
   py -3.13 -m venv .venv
   & .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   & .\.venv\Scripts\python.exe start_service.py
   ```

2. 保持服务运行。在 VS Code 的扩展视图菜单中选择“从 VSIX 安装”，选择本目录的 [seeda-experience-assistant-0.3.2.vsix](./seeda-experience-assistant-0.3.2.vsix)。从“文件 → 打开文件夹”打开本目录内的 [示例项目](./示例项目) 的副本，信任该示例工作区。
3. 在 VS Code 的工作区设置中把 `seeda.pythonPath` 设为上一步 `.venv\Scripts\python.exe` 的完整路径。运行命令“SEED-A：检查后端连接”。默认地址为 `http://127.0.0.1:8765`。使用自己的项目时请选择装有该项目依赖与 pytest 的解释器。

## 保存和复用一条经验

1. 打开 `labels.py`，选中 `normalize_label` 的完整函数，运行“SEED-A：用项目 pytest 验证并保存经验”。写下“规范化标签空格与大小写”，选择 `test_labels.py`。预期 3 项通过。
2. 打开 `练习/reuse_target.py`，选中同名函数，先用 `练习/check_reuse.py` 验证当前实现。预期 1 项失败。
3. 保持目标函数的选区，运行“SEED-A：预览项目经验差异”，搜索“规范化标签空格与大小写”。也可以按标题浏览本项目此版本的已验证经验。核对差异，再选择“采纳预览并保存”。
4. 在采纳的函数内重新运行同一测试，预期 1 项通过。可以查看来源、版本和测试结果，或使用“撤销上一次采纳”恢复原实现。

服务使用本机持久化目录。运行 `start_service.py --data-dir 路径` 可指定独立经验库，按 Ctrl+C 结束服务。再次使用时执行相同启动命令。

## 校验与许可

安装包 SHA-256 为 `2ea6618fe1a54c9d4c06a608fefd73c9cdf6734bee894cf5de24d4ad727e7e2f`。可用 `Get-FileHash .\seeda-experience-assistant-0.3.2.vsix` 核验。[原发行文件摘要](./发行文件摘要.json) 列出了服务源码、示例和安装包的校验值。项目代码适用 [MIT 许可](./LICENSE.txt)，安装包内保留所用 npm 依赖的原始许可证。[扩展源码](../../src/prototype/README.md)
