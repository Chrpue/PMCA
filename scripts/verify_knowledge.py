import os
import sys
import requests
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any

from loguru import logger


def setup_logger():
    """配置Loguru日志记录器。"""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        ),
    )


class KnowledgeVerifier:
    """
    一个用于验证LightRAG中知识元数据完整性的工具。
    """

    def __init__(self, workspace: str):
        self.workspace = workspace.lower()
        self.base_url = self._get_server_url()
        if not self.base_url:
            raise EnvironmentError(
                f"LightRAG server URL for workspace '{self.workspace}' not found. "
                f"Set LIGHTRAG_SERVER_{self.workspace.upper()} in your .env file."
            )

        self.docs_endpoint = f"{self.base_url.rstrip('/')}/documents"
        self.headers = {"accept": "application/json"}
        logger.info(f"Knowledge Verifier initialized for workspace: '{self.workspace}'")

    def _get_server_url(self) -> Optional[str]:
        """从环境变量中发现服务器URL。"""
        return os.getenv(f"LIGHTRAG_SERVER_{self.workspace.upper()}")

    def verify_metadata(self):
        """
        连接到LightRAG，获取所有文档记录，并验证其元数据。
        """
        logger.info(
            f"Fetching all documents from workspace '{self.workspace}' for verification..."
        )
        try:
            response = requests.get(
                self.docs_endpoint, headers=self.headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch documents from LightRAG: {e}")
            sys.exit(1)

        all_docs: List[Dict[str, Any]] = []
        for status, docs_list in data.get("statuses", {}).items():
            all_docs.extend(docs_list)

        if not all_docs:
            logger.warning(
                "No documents found in the LightRAG workspace. Nothing to verify."
            )
            return

        logger.info(
            f"Found a total of {len(all_docs)} documents. Now verifying metadata..."
        )

        perfect_docs = 0
        warning_docs = 0
        error_docs = 0

        # 定义元数据检查项
        required_keys = ["owner_agent", "knowledge_type", "task_keywords"]

        print("-" * 80)
        for doc in all_docs:
            file_path = doc.get("file_path", "N/A")
            doc_id = doc.get("id", "N/A")
            metadata = doc.get("metadata", {})

            # LightRAG的内置元数据和我们注入的元数据是分开的。
            # 我们的元数据是在文件内容中，需要LightRAG的解析器提取。
            # LightRAG本身似乎不会把我们文件里的元数据直接暴露在顶层的metadata字段。
            # 但我们可以通过content_summary来验证。
            content_summary = doc.get("content_summary", "")

            errors = []

            # 验证1: 检查content_summary是否包含了我们的元数据格式
            if (
                "owner_agent" not in content_summary
                or "knowledge_type" not in content_summary
            ):
                errors.append(
                    "Content summary does not seem to contain standard YAML front matter."
                )

            # 验证2: 检查顶层是否有file_path字段
            if not doc.get("file_path"):
                errors.append("Top-level 'file_path' is missing or empty.")

            if not errors:
                logger.success(f"✅ PASSED: '{file_path}' (ID: {doc_id[:12]}...)")
                perfect_docs += 1
            else:
                logger.error(f"❌ FAILED: '{file_path}' (ID: {doc_id[:12]}...)")
                error_docs += 1
                for error in errors:
                    logger.error(f"   - Issue: {error}")

        print("-" * 80)
        logger.info("Verification Summary:")
        logger.success(f"  - Documents with valid metadata structure: {perfect_docs}")
        logger.error(f"  - Documents with errors: {error_docs}")

        if error_docs == 0:
            logger.info(
                "\n🎉 All documents appear to have been ingested correctly with their metadata!"
            )
        else:
            logger.warning(
                "\nSome documents have issues. Please review the errors above."
            )


def main():
    """主函数，解析命令行参数并启动验证器。"""
    parser = argparse.ArgumentParser(
        description="A tool to verify knowledge metadata in a LightRAG server.",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        type=str,
        required=True,
        help="The target LightRAG workspace (e.g., 'app', 'strategy').",
    )

    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass  # .env is optional

    try:
        verifier = KnowledgeVerifier(workspace=args.workspace)
        verifier.verify_metadata()
    except EnvironmentError as e:
        logger.error(e)
        sys.exit(1)


if __name__ == "__main__":
    setup_logger()
    main()
