#!/bin/bash

# 虚拟环境路径
VENV_PATH="./.venv"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_PATH" ]; then
    echo "错误：虚拟环境 '$VENV_PATH' 不存在。"
    echo "请确保虚拟环境已创建，或者修改脚本中的 VENV_PATH。"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 检查激活是否成功
if [ $? -ne 0 ]; then
    echo "错误：激活虚拟环境失败。"
    exit 1
fi

echo "虚拟环境已激活。运行 gradiowebsocket.py..."

# 运行 gradiowebsocket.py
python gradiowebsocket.py

# 运行完毕后，可以选择性地退出虚拟环境
# deactivate

echo "gradiowebsocket.py 运行完毕。"
