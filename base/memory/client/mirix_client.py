import os
import requests
import json
from typing import List, Dict, Optional, Any
from loguru import logger


class PMCAMirixClient:
    """
    终极版 Mirix API 客户端。
    支持用户切换、直接记忆更新，以及读取所有类型的记忆。
    **所有更新操作现在都会严格检查逻辑成功标志。**
    """

    def __init__(self):
        # ... (init 和 _make_request 保持不变) ...
        self.base_url = os.getenv("MIRIX_SERVER")
        if not self.base_url:
            raise ValueError("环境变量 'MIRIX_SERVER' 未设置，无法连接到Mirix服务。")
        self.session = requests.Session()
        self.active_user_id: Optional[str] = None

    def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        url = self.base_url.rstrip("/") + endpoint
        try:
            logger.debug(f"向Mirix发送请求: {method.upper()} {url} | 参数: {kwargs}")
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            if response.status_code == 200 and response.content:
                if response.text == "{}":
                    return {"success": True, "data": "Empty object returned"}
                return response.json()
            return {"success": True, "status_code": response.status_code}
        except requests.exceptions.HTTPError as http_err:
            logger.error(
                f"Mirix API请求失败! 状态码: {http_err.response.status_code}, URL: {url}"
            )
            logger.error(f"错误详情: {http_err.response.text}")
        except requests.exceptions.RequestException as req_err:
            logger.critical(f"连接Mirix服务时发生严重错误: {req_err}")
        return None

    def check_health(self) -> bool:
        response = self._make_request("get", "/health")
        return response is not None

    def list_users(self) -> List[Dict[str, Any]]:
        response = self._make_request("get", "/users")
        users = response.get("users", []) if response else []
        for user in users:
            if user.get("is_active"):
                self.active_user_id = user.get("id")
                break
        return users

    def create_user(self, name: str) -> Optional[Dict[str, Any]]:
        payload = {"name": name, "set_as_active": False}
        response = self._make_request("post", "/users/create", json=payload)
        return response.get("user") if response and response.get("success") else None

    def switch_user(self, user_id: str) -> bool:
        logger.info(f"正在切换 Mirix 的激活用户为: {user_id}")
        payload = {"user_id": user_id}
        response = self._make_request("post", "/users/switch", json=payload)
        if response and response.get("success"):
            self.active_user_id = user_id
            logger.success(f"成功切换激活用户为: {user_id}")
            return True
        logger.error(f"切换用户 {user_id} 失败。响应: {response}")
        return False

    def send_message(self, message: str, user_id: str) -> Optional[Dict[str, Any]]:
        payload = {"message": message, "user_id": user_id}
        return self._make_request("post", "/send_message", json=payload)

    def update_persona(self, persona_text: str, user_id: str) -> bool:
        logger.info(f"为 User ID '{user_id}' 更新 Persona...")
        payload = {"text": persona_text, "user_id": user_id}
        response = self._make_request("post", "/personas/update", json=payload)
        # **严格检查逻辑成功**
        if response and response.get("success"):
            logger.success(f"Persona for user '{user_id}' updated.")
            return True
        logger.error(f"更新 Persona 失败 for user '{user_id}'. 响应: {response}")
        return False

    def update_core_memory(self, label: str, text: str) -> bool:
        logger.info(f"为当前激活用户更新核心记忆 (Label: {label})...")
        payload = {"label": label, "text": text}
        response = self._make_request("post", "/core_memory/update", json=payload)
        # **严格检查逻辑成功**
        if response and response.get("success"):
            logger.success(f"Core memory '{label}' updated for active user.")
            return True
        logger.error(f"更新核心记忆 '{label}' 失败 for active user. 响应: {response}")
        return False

    # ... (get_..._memory 方法保持不变) ...
    def get_core_memory(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request("get", "/memory/core", params={"user_id": user_id})

    def get_episodic_memory(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request(
            "get", "/memory/episodic", params={"user_id": user_id}
        )

    def get_semantic_memory(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request(
            "get", "/memory/semantic", params={"user_id": user_id}
        )

    def get_procedural_memory(self, user_id: str) -> Optional[Dict[str, Any]]:
        return self._make_request(
            "get", "/memory/procedural", params={"user_id": user_id}
        )

