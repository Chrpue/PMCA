import redis
import sys

# --- Redis 配置 ---
REDIS_HOST = "localhost"
REDIS_PORT = 36379
REDIS_DB = 0
REDIS_PASSWORD = "pmcaredis"  # 如果你的 Redis 没有密码

print("--- Redis 连接测试 ---")

try:
    # 1. 创建 Redis 连接
    print(f"正在尝试连接到 Redis 服务器: {REDIS_HOST}:{REDIS_PORT}...")
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True,  # 这样返回的值就是字符串，而不是字节
    )

    # 2. 测试连接 (ping)
    r.ping()
    print("✅ 连接成功！")

    # 3. 测试读写操作
    print("\n--- 读写测试 ---")
    test_key = "pmca_test_key"
    test_value = "It works!"

    print(f"写入数据: key='{test_key}', value='{test_value}'")
    r.set(test_key, test_value)

    retrieved_value = r.get(test_key)
    print(f"读取数据: key='{test_key}', value='{retrieved_value}'")

    if retrieved_value == test_value:
        print("✅ 读写成功！数据一致。")
    else:
        print("❌ 读写失败！数据不匹配。")
        sys.exit(1)

    # 4. 清理测试数据
    r.delete(test_key)
    print("\n测试数据已清理。")

except redis.exceptions.ConnectionError as e:
    print(f"❌ 连接失败: {e}")
    print("\n请确认：")
    print("1. 您是否已经通过 `docker run ...` 命令启动了 Redis 容器？")
    print("2. 在另一个终端运行 `docker ps`，检查 pmca-redis 容器是否正在运行。")
    print("3. .env 文件中的 REDIS_HOST 和 REDIS_PORT 是否正确配置？")
    sys.exit(1)
except Exception as e:
    print(f"发生未知错误: {e}")
    sys.exit(1)
