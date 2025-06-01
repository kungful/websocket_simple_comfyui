# 如果你接收到图像是噪点图，那么请将comfyui manage的k采样器预览功能关闭，改称none（very fast）就能正常接收到完整的图像

import gradio as gr
import websocket # NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import io
from PIL import Image
import os
import random # Added for random seed generation

# --- Global Configuration ---
def get_json_files_in_root(directory="."):
    """扫描指定目录下的JSON文件列表"""
    files = []
    try:
        for f_name in os.listdir(directory):
            if os.path.isfile(os.path.join(directory, f_name)) and f_name.lower().endswith(".json"):
                files.append(f_name)
    except Exception as e:
        print(f"Error scanning for JSON files: {e}")
    return files

AVAILABLE_WORKFLOW_FILES = get_json_files_in_root()

# --- ComfyUI API Call Functions ---
def queue_prompt(prompt, request_url, client_id):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(request_url, data=data)
    try:
        response = urllib.request.urlopen(req)
        return json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Error queueing prompt (URLError): {e} to {request_url}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding queue response (JSONDecodeError): {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in queue_prompt: {e}")
        return None


def get_images_from_websocket(ws, prompt_id_to_wait_for, target_image_node_name):
    output_images = {}
    current_node_for_image = ""
    print(f"Waiting for images from prompt_id: {prompt_id_to_wait_for} on node: {target_image_node_name}")

    while True:
        try:
            out = ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'status':
                    pass
                elif message['type'] == 'executing':
                    data = message['data']
                    if data.get('prompt_id') == prompt_id_to_wait_for:
                        if data['node'] is None:
                            print(f"Execution finished for prompt_id: {prompt_id_to_wait_for}")
                            if not output_images.get(target_image_node_name):
                                print(f"Warning: No image received from target node '{target_image_node_name}' before execution finished.")
                            break
                        else:
                            current_node_for_image = data['node']
            elif isinstance(out, bytes):
                if current_node_for_image == target_image_node_name or not output_images.get(target_image_node_name): # Prioritize target, but accept if nothing else has been stored for target yet
                    images_output_list = output_images.get(target_image_node_name, [])
                    images_output_list.append(out[8:]) # First 8 bytes are header
                    output_images[target_image_node_name] = images_output_list
                    print(f"Image received and stored for target node '{target_image_node_name}'. Total for this node: {len(images_output_list)}")

        except websocket.WebSocketConnectionClosedException:
            print("WebSocket connection closed.")
            break
        except ConnectionResetError:
            print("WebSocket connection reset by peer.")
            break
        except json.JSONDecodeError as e:
            print(f"Error decoding WebSocket JSON message: {e} - Message: {out if isinstance(out, str) else '<binary_data>'}")
        except Exception as e:
            print(f"WebSocket error during recv: {e}")
            break
    return output_images


# --- Main Generation Function ---
def generate_image_via_comfyui(
    selected_workflow_file,
    server_addr_input,
    additional_context_input,
    seed_input, # This is the seed from the UI
    image_output_node_id_from_ui
):
    if not selected_workflow_file:
        return None, "错误：请先选择一个工作流JSON文件。"
    if not os.path.exists(selected_workflow_file):
        workflow_path = os.path.join(".", selected_workflow_file)
        if not os.path.exists(workflow_path):
             return None, f"错误：选择的工作流文件 '{selected_workflow_file}' 不存在。"
    else:
        workflow_path = selected_workflow_file

    parsed_url = urllib.parse.urlparse(server_addr_input)
    scheme = parsed_url.scheme
    netloc = parsed_url.netloc
    path = parsed_url.path.rstrip('/')

    if not scheme:
        if not netloc and path:
            parts = path.split('/', 1)
            netloc = parts[0]
            path = '/' + parts[1] if len(parts) > 1 else ''
            path = path.rstrip('/')
        http_scheme = "http"
        ws_scheme = "ws"
    elif scheme.lower() == "https":
        http_scheme = "https"
        ws_scheme = "wss"
    elif scheme.lower() == "http":
        http_scheme = "http"
        ws_scheme = "ws"
    else:
        print(f"Warning: Unknown scheme '{scheme}' in server address. Defaulting to http/ws.")
        http_scheme = "http"
        ws_scheme = "ws"

    if not netloc:
        return None, f"无法从输入 '{server_addr_input}' 解析服务器地址/主机名。"

    prompt_request_url = urllib.parse.urlunparse((http_scheme, netloc, f"{path}/prompt", '', '', ''))
    websocket_url_base = urllib.parse.urlunparse((ws_scheme, netloc, f"{path}/ws", '', '', ''))

    client_id = str(uuid.uuid4())
    websocket_connect_url = f"{websocket_url_base}?clientId={client_id}"
    
    print(f"Attempting to connect to ComfyUI API at: {prompt_request_url}")
    print(f"Attempting to connect to WebSocket at: {websocket_connect_url}")

    ws = websocket.WebSocket()
    try:
        ws.connect(websocket_connect_url)
        print(f"WebSocket connected to {websocket_connect_url}")
    except Exception as e:
        return None, f"无法连接WebSocket ({websocket_connect_url}): {e}"

    try:
        with open(workflow_path, 'r', encoding='utf-8') as f:
            prompt = json.loads(f.read())
        print(f"Successfully loaded workflow from: {workflow_path}")
    except Exception as e:
        ws.close()
        print(f"Error loading or parsing workflow file '{workflow_path}': {e}")
        return None, f"加载或解析工作流文件时出错: {e}"

    # Modify GeminiFlash node
    gemini_flash_node_id = None
    for node_id, node_data in prompt.items():
        if node_data.get("class_type") == "GeminiFlash":
            gemini_flash_node_id = node_id
            break # Found the first one

    if gemini_flash_node_id:
        if "inputs" in prompt[gemini_flash_node_id] and "Additional_Context" in prompt[gemini_flash_node_id]["inputs"]:
            prompt[gemini_flash_node_id]["inputs"]["Additional_Context"] = additional_context_input
            print(f"Applied 'Additional_Context': '{additional_context_input}' to GeminiFlash node '{gemini_flash_node_id}'")
        else:
            print(f"Warning: GeminiFlash node '{gemini_flash_node_id}' found, but 'Additional_Context' input not present or 'inputs' field missing.")
    else:
        print("Warning: No 'GeminiFlash' node found in the workflow. 'Additional_Context' from UI not applied.")

    # --- MODIFIED SECTION FOR Hua_gradio_Seed ---
    found_hua_seed_node_id = None
    for node_id_iter, node_data_iter in prompt.items():
        if node_data_iter.get("class_type") == "Hua_gradio_Seed":
            found_hua_seed_node_id = node_id_iter
            break # Use the first one found

    if found_hua_seed_node_id:
        if "inputs" in prompt[found_hua_seed_node_id] and "seed" in prompt[found_hua_seed_node_id]["inputs"]:
            # Generate a random seed as requested, ignoring the seed_input from UI for this node
            random_seed_value = random.randint(0, 2**64 - 1) # Generate a large random seed
            prompt[found_hua_seed_node_id]["inputs"]["seed"] = random_seed_value
            print(f"Dynamically found Hua_gradio_Seed node '{found_hua_seed_node_id}'. Applied *random* seed: {random_seed_value}. (UI seed input '{seed_input}' from Gradio is ignored for this specific node type).")
        else:
            print(f"Warning: Hua_gradio_Seed node '{found_hua_seed_node_id}' found, but its 'inputs' field or 'seed' key is missing. Random seed not applied.")
    else:
        # The seed_input from the UI is not used if Hua_gradio_Seed node isn't found by this logic.
        # You could add other logic here if seed_input should be used for other node types/IDs.
        print(f"Warning: No 'Hua_gradio_Seed' node found in the workflow. Cannot apply a targeted random seed. The UI seed value '{seed_input}' was not applied to a Hua_gradio_Seed node.")
    # --- END OF MODIFIED SECTION ---
    
    actual_image_output_node_id = None
    if image_output_node_id_from_ui and image_output_node_id_from_ui.strip():
        user_id = image_output_node_id_from_ui.strip()
        if user_id in prompt and prompt[user_id].get("class_type") == "SaveImageWebsocket":
            actual_image_output_node_id = user_id
            print(f"Using user-specified SaveImageWebsocket node ID: '{actual_image_output_node_id}'")
        else:
            print(f"Warning: User-specified SaveImageWebsocket ID '{user_id}' is invalid or not a SaveImageWebsocket node. Attempting auto-detection.")

    if not actual_image_output_node_id:
        found_auto_node = False
        for node_id, node_data in prompt.items():
            if node_data.get("class_type") == "SaveImageWebsocket":
                actual_image_output_node_id = node_id
                found_auto_node = True
                print(f"Auto-detected SaveImageWebsocket node ID: '{actual_image_output_node_id}' (using the first one found).")
                break
        if not found_auto_node:
             print("Info: Auto-detection for SaveImageWebsocket node did not find any.")

    if not actual_image_output_node_id:
        ws.close()
        return None, f"错误: 在工作流 '{selected_workflow_file}' 中未能找到任何 'SaveImageWebsocket' 类型的节点 (用户也未提供有效的ID)."

    queued_data = queue_prompt(prompt, prompt_request_url, client_id)
    if not queued_data or 'prompt_id' not in queued_data:
        ws.close()
        return None, f"无法提交工作流 ({prompt_request_url}) 或获取prompt_id."
    prompt_id = queued_data['prompt_id']
    print(f"Prompt queued with ID: {prompt_id}")

    all_output_images = get_images_from_websocket(ws, prompt_id, actual_image_output_node_id)
    ws.close()
    print("WebSocket closed.")

    if all_output_images and actual_image_output_node_id in all_output_images:
        image_data_list = all_output_images[actual_image_output_node_id]
        if image_data_list:
            try:
                image = Image.open(io.BytesIO(image_data_list[0]))
                return image, "图像生成成功。"
            except Exception as e:
                print(f"Error opening image from bytes: {e}")
                return None, f"打开图像时出错: {e}"
        else:
            return None, f"节点 '{actual_image_output_node_id}' 未返回图像数据。"
    else:
        return None, f"未从节点 '{actual_image_output_node_id}' 收到期望的图像数据。"


# --- Gradio UI Definition ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    with gr.Row():
        with gr.Column():
            gr.Markdown("# ComfyUI Workflow Runner (专注版 v2.2 - URL Enhanced & Random Seed)") # Minor title change
            gr.Markdown(
                "从本地选择一个JSON工作流，输入以下特定参数，然后生成图像。\n"
                "**确保**: \n"
                "1. 选定的JSON工作流包含一个 `GeminiFlash` 节点 (用于 'Additional Context')。\n"
                "2. 如果工作流包含 `Hua_gradio_Seed` 节点, **脚本将自动为其填入随机种子**。\n" #MODIFIED
                "3. 工作流中必须包含至少一个 `SaveImageWebsocket` 类型的节点，用于通过WebSocket输出图像。\n"
                "4. ComfyUI 服务器地址可以是 `127.0.0.1:8188`，也可以是完整的URL，如 `https://your-domain.com/comfyui-path`。"
            )
        
            with gr.Row():
                workflow_file_dropdown = gr.Dropdown(
                    label="选择工作流 JSON 文件",
                    choices=AVAILABLE_WORKFLOW_FILES,
                    value=AVAILABLE_WORKFLOW_FILES[0] if AVAILABLE_WORKFLOW_FILES else None,
                    interactive=True
                )
                server_address_input = gr.Textbox(
                    label="ComfyUI 服务器地址", 
                    value="127.0.0.1:8188", 
                    placeholder="例如: 127.0.0.1:8188 或 https://your-domain.com/comfyui"
                )
        
            with gr.Row():
                additional_context_ui_input = gr.Textbox(label="输入要造句的单词", value="boy", scale=3)
                # --- MODIFIED LABEL for seed_ui_input ---
                seed_ui_input = gr.Number(
                    label="种子参数 (提示: 若工作流含'Hua_gradio_Seed'节点, 此处设置将被自动生成的随机种子覆盖)", 
                    value=12345, 
                    precision=0, 
                    scale=1
                )
                # --- END OF MODIFIED LABEL ---
        
            image_output_node_id_ui_input = gr.Textbox(
                label="SaveImageWebsocket 节点ID (可选)",
                value="",
                placeholder="留空则自动检测, 或指定特定ID (如 '16')"
            )
            status_message_display = gr.Textbox(label="状态", lines=3, interactive=False)    
        
    
            gr.Markdown("---")
            gr.Markdown("提示：如果工作流中有多个 `SaveImageWebsocket` 节点，请在上方“SaveImageWebsocket 节点ID”字段指定要使用哪一个，否则将使用自动检测到的第一个。如果自动检测失败或指定ID无效，程序将报错。")        
    
        
    
    
        with gr.Column():        
            output_image_display = gr.Image(label="生成的图像", type="pil", show_download_button=True, height=768, width=1024) 

            generate_button = gr.Button("生成图像", variant="primary")
    
            generate_button.click(
                fn=generate_image_via_comfyui,
                inputs=[
                    workflow_file_dropdown,
                    server_address_input,
                    additional_context_ui_input,
                    seed_ui_input, # Still passed, but might be ignored by logic for Hua_gradio_Seed
                    image_output_node_id_ui_input
                ],
                outputs=[output_image_display, status_message_display]
            )

if __name__ == "__main__":
    if not AVAILABLE_WORKFLOW_FILES:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!! 警告: 在当前目录未找到任何 .json 工作流文件。                      !!")
        print("!! 请将ComfyUI工作流 (API格式) 保存为 .json 文件并放置于此脚本同目录下。 !!")
        print("!! 你可以从ComfyUI界面点击 'Save (API Format)' 按钮来导出。            !!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
    demo.launch()