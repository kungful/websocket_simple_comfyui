# ComfyUI Workflow Runner (专注版 v2.2)

这是一个基于 Gradio 的 Web UI 工具，用于连接到 ComfyUI 服务器并通过 WebSocket 运行图像生成工作流。用户可以选择本地的 ComfyUI 工作流 JSON 文件，调整特定参数，查看生成的图像。
![项目预览](https://github.com/kungful/websocket_simple_comfyui/blob/b0474bf31c5973a96392dd6d4c376a7ac42c7f62/preview.png?raw=true)
## 灵感来源 (Inspiration)

本项目的 WebSocket 通信和 ComfyUI 交互部分的核心实现思路，受到了 ComfyUI 官方提供的示例脚本 [websockets_api_example_ws_images.py](https://github.com/comfyanonymous/ComfyUI/blob/6d46bb4b4c9db3bce46b2838c50252551330eba7/script_examples/websockets_api_example_ws_images.py) 的启发。特别感谢 ComfyUI 作者 `comfyanonymous` 提供的清晰示例。

## 主要功能

* **Gradio Web 界面**: 提供简单易用的图形界面与 ComfyUI 交互。
* **工作流选择**: 自动扫描并列出脚本所在目录下的 ComfyUI 工作流 JSON 文件供用户选择。
* **动态参数注入**:
    * 支持为工作流中的 `GeminiFlash` 节点填入 "Additional_Context"（例如，用于造句的单词）。
    * 如果工作流包含 `Hua_gradio_Seed` 节点，脚本将**自动为其填入一个随机种子**，此时UI上输入的种子值会被忽略。
* **灵活的服务器地址配置**: 支持标准IP地址（如 `127.0.0.1:8188`）以及完整的URL路径（如 `https://your-domain.com/comfyui-path`）。
* **图像输出**: 通过工作流中的 `SaveImageWebsocket` 节点接收并显示生成的图像。支持自动检测或手动指定节点ID。
* **状态反馈**: 在UI上显示操作状态和错误信息。

## 先决条件

1.  **Python**: 建议使用 Python 3.8 或更高版本。
2.  **ComfyUI**: 需要一个正在运行的 ComfyUI 实例。
3.  **ComfyUI 工作流**:
    * 工作流文件必须是以 **API Format** 保存的 `.json` 文件。您可以从 ComfyUI 界面点击 "Save (API Format)" 按钮来导出。
    * 工作流中**必须**包含至少一个 `SaveImageWebsocket` 类型的节点用于图像输出。
    * 如果希望使用“额外上下文”功能，工作流中应包含一个名为 `GeminiFlash` 的节点，且该节点有 "Additional\_Context" 输入项。
    * 如果希望脚本自动应用随机种子，工作流中应包含一个名为 `Hua_gradio_Seed` 的节点，且该节点有 "seed" 输入项。

## 安装

1.  **克隆或下载仓库/脚本**:
    获取 `gradiowebsocket.py` 脚本文件。

2.  **安装依赖**:
    创建一个 `requirements.txt` 文件，内容如下：
    ```txt
    gradio
    websocket-client
    Pillow
    ```
    然后通过 pip 安装：
    ```bash
    pip install -r requirements.txt
    ```

## 如何使用
0.  请先在comfyui中先跑通工作流，llm也可以使用本地，默认我使用的是gemini,目前免费的api。
1.  **放置工作流文件**: 将您导出的 ComfyUI 工作流 `.json` 文件（API格式）放置在与 `gradiowebsocket.py` 脚本相同的目录下。如果未找到任何 JSON 文件，脚本启动时会给出警告。

2.  **运行脚本**:
    ```bash
    python gradiowebsocket.py
    ```

3.  **打开 Web 界面**:
    脚本启动后，通常会在控制台输出一个本地 URL (例如 `http://127.0.0.1:7860`)。在浏览器中打开此 URL。

4.  **配置参数**:
    * **选择工作流 JSON 文件**: 从下拉列表中选择一个位于脚本目录下的工作流文件。
    * **ComfyUI 服务器地址**: 输入 ComfyUI 服务器的地址 (默认为 `127.0.0.1:8188`)。
    * **输入要造句的单词**: 如果您的工作流包含 `GeminiFlash` 节点并希望使用此功能，请在此处输入文本 (默认为 `boy`)。
    * **种子参数**: 输入一个种子值 (默认为 `12345`)。
        * **重要提示**: 若工作流含 `Hua_gradio_Seed` 节点，此处设置将被脚本自动生成的随机种子覆盖。
    * **SaveImageWebsocket 节点ID (可选)**:
        * 如果工作流中有多个 `SaveImageWebsocket` 节点，请在此字段指定要使用哪一个的节点ID (例如 `16`)。
        * 如果留空，脚本将自动检测并使用找到的第一个 `SaveImageWebsocket` 节点。
        * 如果自动检测失败或指定的ID无效，程序将报错。

5.  **生成图像**: 点击 "生成图像" 按钮。生成的图像和状态信息会显示在右侧。

## 重要提示

* **图像噪点问题**: 脚本注释中提到：“如果你接收到图像是噪点图，那么请将comfyui manage的k采样器预览功能关闭，改称none（very fast）就能正常接收到完整的图像”。
* **节点命名**: 脚本通过节点的 `class_type` (例如 `GeminiFlash`, `Hua_gradio_Seed`, `SaveImageWebsocket`) 来识别和操作特定节点。请确保您工作流中对应节点的类型名称与脚本预期一致。

## 项目名称由来

脚本UI标题为 "ComfyUI Workflow Runner (专注版 v2.2 - URL Enhanced & Random Seed)"，表明这是一个专注于特定增强功能（如改进的URL处理和随机种子特性）的版本。

---

希望这份说明能帮助您更好地了解和使用这个项目！
