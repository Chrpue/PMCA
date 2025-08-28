import requests
import json
import time
import uuid

# Mirix API的基础URL
BASE_URL = "http://localhost:47283"


def print_response(name, response):
    """格式化并打印API响应"""
    print(f"--- [测试] {name} ---")
    try:
        response.raise_for_status()  # 如果HTTP状态码是4xx或5xx，则抛出异常
        print(f"状态码: {response.status_code} (成功)")
        print("响应内容 (JSON):")
        # 使用 ensure_ascii=False 来正确显示中文
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except requests.exceptions.HTTPError as http_err:
        print(f"请求失败! 状态码: {response.status_code}")
        print(f"错误详情: {response.text}")
    except json.JSONDecodeError:
        print("响应内容 (非JSON):")
        print(response.text)
    except requests.exceptions.RequestException as req_err:
        print(f"请求时发生严重错误: {req_err}")
    print("-" * (len(name) + 10))
    print("\n")


def check_health():
    """测试 /health 接口"""
    print("1. 正在进行健康检查...")
    response = requests.get(f"{BASE_URL}/health")
    print_response("服务健康检查", response)
    return response.ok


def list_users():
    """测试 /users 接口，获取所有用户"""
    print("2. 正在获取当前所有用户列表...")
    response = requests.get(f"{BASE_URL}/users")
    print_response("获取用户列表", response)
    if response.ok:
        return response.json().get("users", [])
    return []


def create_user(name: str):
    """测试 /users/create 接口，创建一个新用户"""
    print(f"3. 正在创建一个名为 '{name}' 的新用户...")
    payload = {"name": name, "set_as_active": False}  # 我们先不设为激活，手动切换
    response = requests.post(f"{BASE_URL}/users/create", json=payload)
    print_response(f"创建用户 '{name}'", response)
    if response.ok:
        return response.json().get("user")
    return None


def test_send_message_default_user():
    """
    测试场景1: 不带 user_id 发送消息
    服务器应自动使用当前活跃的用户 (通常是默认用户)
    """
    print("4. [场景 A] 正在测试发送消息 (使用默认活跃用户)...")
    payload = {"message": "你好，我是默认用户，请问现在几点了？"}
    response = requests.post(f"{BASE_URL}/send_message", json=payload)
    print_response("发送消息 (默认用户)", response)


def test_send_message_specific_user(user_id: str):
    """
    测试场景2: 带 user_id 发送消息
    服务器应切换到指定的 'user_id' 的上下文来处理消息
    """
    if not user_id:
        print("无法进行场景B测试，因为没有获取到新用户的ID。")
        return

    print(f"5. [场景 B] 正在测试发送消息 (指定用户ID: {user_id})...")
    payload = {
        "message": "你好，我是刚刚创建的新用户，你能记住我吗？",
        "user_id": user_id,
    }
    response = requests.post(f"{BASE_URL}/send_message", json=payload)
    print_response(f"发送消息 (指定用户 '{user_id}')", response)


if __name__ == "__main__":
    print("=" * 40)
    print("开始对修复后的 Mirix API 进行全面测试...")
    print("=" * 40 + "\n")

    if not check_health():
        print(
            "健康检查失败！请确保您的Docker容器已通过 'docker-compose up -d' 成功启动。"
        )
    else:
        # 获取初始用户列表
        users_before = list_users()
        time.sleep(1)

        # 创建一个新用户以供测试
        new_user_name = f"tester-{str(uuid.uuid4())[:4]}"
        new_user = create_user(new_user_name)
        new_user_id = new_user.get("id") if new_user else None
        time.sleep(1)

        # 再次获取用户列表，确认新用户已添加
        users_after = list_users()
        time.sleep(1)

        # --- 执行核心测试场景 ---

        # 场景 A: 模拟没有 user_id 的普通请求
        test_send_message_default_user()
        time.sleep(1)

        # 场景 B: 模拟切换用户的请求
        test_send_message_specific_user(new_user_id)

        print("=" * 40)
        print("所有测试已执行完毕！")
        print("=" * 40)
        print("请检查上面的输出：")
        print("  - 所有请求的'状态码'是否都是 200 (成功)。")
        print(
            f"  - '获取用户列表' 的第二次调用结果中是否包含了用户 '{new_user_name}'。"
        )
        print("  - [场景 A] 和 [场景 B] 是否都成功返回了响应，没有出现500服务器错误。")
