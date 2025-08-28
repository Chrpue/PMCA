import os
import requests
import json
from typing import List, Dict, Optional, Any
from loguru import logger


class PMCAMirixClient:
    """
    用于与在Docker中运行的Mirix记忆服务进行通信的API客户端。
    遵循PMCA项目规范。
    """

    def __init__(self):
        self.base_url = os.getenv("MIRIX_SERVER")
        if not self.base_url:
            raise ValueError("环境变量 'MIRIX_SERVER' 未设置，无法连接到Mirix服务。")

        self.session = requests.Session()
        logger.info(f"PMCAMirixClient 初始化，将连接到 Mirix 服务于: {self.base_url}")

    def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Optional[Dict[str, Any]]:
        url = self.base_url + endpoint
        try:
            logger.debug(
                f"向Mirix发送请求: {method.upper()} {url} | 参数: {kwargs.get('json', {})}"
            )
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            logger.debug(f"从Mirix收到成功响应 ({response.status_code}) from {url}")
            return response.json()
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
        return response is not None and response.get("status") == "healthy"

    def list_users(self) -> List[Dict[str, Any]]:
        response = self._make_request("get", "/users")
        return response.get("users", []) if response else []

    def create_user(self, name: str) -> Optional[Dict[str, Any]]:
        payload = {"name": name, "set_as_active": False}
        response = self._make_request("post", "/users/create", json=payload)
        return response.get("user") if response and response.get("success") else None

    def send_message(self, message: str, user_id: str) -> Optional[Dict[str, Any]]:
        payload = {"message": message, "user_id": user_id}
        return self._make_request("post", "/send_message", json=payload)
