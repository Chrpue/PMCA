import os
import sys
import requests
import argparse
from pathlib import Path
from typing import Set, Dict

from tqdm import tqdm
from loguru import logger


# --- Loguru Logger Setup ---
def setup_logger():
    """配置Loguru日志记录器，提供清晰的控制台输出。"""
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


class KnowledgeSyncer:
    """
    一个智能的知识同步工具，用于将本地的知识目录与远程的LightRAG服务器进行比较和同步。
    核心特性：
    - 幂等性：只会上传新增或变更的文件，可重复安全执行。
    - 工作区支持：通过命令行参数支持不同的知识库工作区。
    """

    def __init__(self, workspace: str):
        self.workspace = workspace.lower()
        self.base_url = self._get_server_url()
        if not self.base_url:
            raise EnvironmentError(
                f"LightRAG server URL for workspace '{self.workspace}' not found. "
                f"Please set LIGHTRAG_SERVER_{self.workspace.upper()} in your environment."
            )

        self.local_knowledge_dir = (
            Path.cwd() / "documents" / self.workspace / "base_knowledge"
        )
        self.docs_endpoint = f"{self.base_url.rstrip('/')}/documents"
        self.upload_endpoint = f"{self.base_url.rstrip('/')}/documents/upload"
        self.headers = {"accept": "application/json"}

        logger.info(f"Syncer initialized for workspace: '{self.workspace}'")
        logger.info(f"Local source directory: '{self.local_knowledge_dir}'")

    def _get_server_url(self) -> str | None:
        """从环境变量中发现服务器URL。"""
        return os.getenv(f"LIGHTRAG_SERVER_{self.workspace.upper()}")

    def get_remote_filenames(self) -> Set[str]:
        """获取LightRAG中所有已处理文件的**文件名**集合，用于后续比对。"""
        logger.info(
            f"Fetching current document status from LightRAG workspace '{self.workspace}'..."
        )
        try:
            response = requests.get(
                self.docs_endpoint, headers=self.headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            remote_filenames = set()
            for status, docs in data.get("statuses", {}).items():
                for doc in docs:
                    if "file_path" in doc and doc["file_path"]:
                        # 我们只关心文件名，因为服务器上的绝对路径对我们没有意义
                        remote_filenames.add(Path(doc["file_path"]).name)

            logger.info(f"Found {len(remote_filenames)} documents in remote workspace.")
            return remote_filenames
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch documents from LightRAG: {e}")
            logger.error("   - Please ensure the service is running and accessible.")
            return set()

    def get_local_files(self) -> Dict[str, Path]:
        """获取本地知识目录下的所有.md文件，返回一个 文件名 -> 文件路径 的字典。"""
        if (
            not self.local_knowledge_dir.exists()
            or not self.local_knowledge_dir.is_dir()
        ):
            logger.warning(
                f"Local knowledge directory '{self.local_knowledge_dir}' not found. Nothing to sync."
            )
            return {}

        local_files_map = {
            md_file.name: md_file for md_file in self.local_knowledge_dir.glob("*.md")
        }
        logger.info(f"Found {len(local_files_map)} local knowledge files.")
        return local_files_map

    def sync(self):
        """
        执行同步操作的核心逻辑：
        1. 获取远程文件名列表。
        2. 获取本地文件列表。
        3. 找出需要上传的文件（本地存在但远程不存在）。
        4. 执行上传。
        """
        remote_filenames = self.get_remote_filenames()
        local_files_map = self.get_local_files()

        if not local_files_map:
            return

        files_to_upload = [
            local_path
            for local_filename, local_path in local_files_map.items()
            if local_filename not in remote_filenames
        ]

        if not files_to_upload:
            logger.success(
                "✅ Knowledge base is already up-to-date. No new files to upload."
            )
            return

        logger.info(
            f"Found {len(files_to_upload)} new file(s) to upload. Starting upload process..."
        )

        failed_uploads = []
        for file_path in tqdm(files_to_upload, desc="Uploading new knowledge"):
            try:
                with open(file_path, "rb") as f:
                    files = {"file": (file_path.name, f.read(), "text/markdown")}
                    response = requests.post(
                        self.upload_endpoint,
                        headers=self.headers,
                        files=files,
                        timeout=60,
                    )
                    response.raise_for_status()
            except requests.exceptions.RequestException as e:
                failed_uploads.append({"file": file_path.name, "error": str(e)})
            except Exception as e:
                failed_uploads.append(
                    {"file": file_path.name, "error": f"Local file read error: {e}"}
                )

        logger.info("--- Sync Complete ---")
        if not failed_uploads:
            logger.success(
                f"Successfully uploaded all {len(files_to_upload)} new file(s)."
            )
        else:
            logger.warning(f"Sync completed with {len(failed_uploads)} failure(s).")
            for failure in failed_uploads:
                logger.error(
                    f"  - File: {failure['file']} | Reason: {failure['error']}"
                )


def main():
    """主函数，解析命令行参数并启动同步器。"""
    parser = argparse.ArgumentParser(
        description="A smart tool to sync a local knowledge directory with a LightRAG server.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-w",
        "--workspace",
        type=str,
        default="app",
        help="The target LightRAG workspace (e.g., 'app', 'strategy'). Default: 'app'.",
    )

    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        load_dotenv()
        logger.info("Loaded environment variables from .env file.")
    except ImportError:
        logger.warning(
            ".env file not found or dotenv not installed, relying on system variables."
        )

    try:
        syncer = KnowledgeSyncer(workspace=args.workspace)
        syncer.sync()
    except EnvironmentError as e:
        logger.error(e)
        sys.exit(1)


if __name__ == "__main__":
    setup_logger()
    main()
