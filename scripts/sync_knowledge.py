import os
import sys
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

from tqdm import tqdm
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
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )


class KnowledgeSyncer:
    """
    一个智能的知识同步工具，用于通过命令行参数指定工作空间和知识类型，
    同步本地知识目录和远程LightRAG服务器。
    """

    def __init__(self, workspace: str, knowledge_type: str):
        self.workspace = workspace.lower()
        self.knowledge_type = knowledge_type.lower()

        # 1. 获取并验证LightRAG服务器地址
        self.base_url = self._get_server_url()
        if not self.base_url:
            raise EnvironmentError(
                f"LightRAG server URL for workspace '{self.workspace}' not found. "
                f"Please set LIGHTRAG_SERVER_{self.workspace.upper()} in your .env file."
            )

        # 2. 构建本地知识源路径
        self.local_knowledge_dir = (
            Path.cwd()
            / "documents"
            / self.workspace
            / f"{self.knowledge_type}_knowledge"
        )

        # 3. 构建容器内的目标输入路径
        self.docker_input_dir = f"/app/data/inputs/{self.workspace}"

        # 4. 构建API端点
        self.docs_endpoint = f"{self.base_url.rstrip('/')}/documents"
        self.upload_endpoint = f"{self.base_url.rstrip('/')}/documents/upload"
        self.headers = {"accept": "application/json"}

        logger.info(f"Syncer initialized for workspace: '{self.workspace}'")
        logger.info(f"Local source directory: '{self.local_knowledge_dir}'")
        logger.info(
            f"Remote target directory (in container): '{self.docker_input_dir}'"
        )

    def _get_server_url(self) -> Optional[str]:
        """从环境变量中发现服务器URL。"""
        return os.getenv(f"LIGHTRAG_SERVER_{self.workspace.upper()}")

    def get_remote_files(self) -> Set[str]:
        """获取LightRAG中所有已处理文件的路径集合。"""
        logger.info("Fetching current document status from LightRAG...")
        try:
            response = requests.get(
                self.docs_endpoint, headers=self.headers, timeout=30
            )
            response.raise_for_status()
            data = response.json()

            remote_paths = set()
            for status, docs in data.get("statuses", {}).items():
                for doc in docs:
                    # 从返回的绝对路径中只取文件名进行比较，因为挂载点可能变化
                    if "file_path" in doc and doc["file_path"]:
                        remote_paths.add(Path(doc["file_path"]).name)

            logger.info(
                f"Found {len(remote_paths)} documents in remote workspace '{self.workspace}'."
            )
            return remote_paths
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Failed to fetch documents from LightRAG: {e}")
            logger.error("   - Please ensure the service is running and accessible.")
            return set()

    def get_local_files(self) -> Dict[str, Path]:
        """获取本地知识目录下的所有.md文件。"""
        if (
            not self.local_knowledge_dir.exists()
            or not self.local_knowledge_dir.is_dir()
        ):
            logger.error(
                f"Local knowledge directory '{self.local_knowledge_dir}' not found. Cannot sync."
            )
            return {}

        local_files_map = {
            md_file.name: md_file for md_file in self.local_knowledge_dir.glob("*.md")
        }

        logger.info(
            f"Found {len(local_files_map)} local knowledge files in '{self.local_knowledge_dir}'."
        )
        return local_files_map

    def sync(self):
        """执行同步操作：比较本地和远程，并上传差异文件。"""
        remote_filenames = self.get_remote_files()
        local_files_map = self.get_local_files()

        if not local_files_map:
            return

        files_to_upload = []
        for local_filename, local_path in local_files_map.items():
            if local_filename not in remote_filenames:
                files_to_upload.append(local_path)

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
        required=True,
        help="The target LightRAG workspace (e.g., 'app', 'strategy', 'gas').\n"
        "This determines which server to connect to and the remote directory.",
    )
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        required=True,
        choices=["base"],  # 您可以在这里扩展支持的类型, e.g., ['base', 'extended']
        help="The type of knowledge to sync (e.g., 'base').\n"
        "This determines the local source sub-directory.",
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
        syncer = KnowledgeSyncer(workspace=args.workspace, knowledge_type=args.type)
        syncer.sync()
    except EnvironmentError as e:
        logger.error(e)
        sys.exit(1)


if __name__ == "__main__":
    setup_logger()
    main()
