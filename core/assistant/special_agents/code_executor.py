import os
import json
from autogen_agentchat.agents import CodeExecutorAgent
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor


class PMCACodeExecutor:
    def __init__(self):
        self._image = os.getenv("DOCKER_IMAGE", default="python:3-slim")
        self._container_name = os.getenv("DOCKER_CONTAINER_NAME")
        self._timeout = int(os.getenv("DOCKER_TIMEOUT", default=60))
        self._work_dir = os.getenv("DOCKER_WORK_DIR")
        self._auto_remove = os.getenv("DOCKER_AUTO_REMOVE")
        self._stop_container = os.getenv("DOCKER_STOP_CONTAINER")
        self._extra_volumes = os.getenv("DOCKER_EXTRA_VOLUMES", default="")

        self._executor = DockerCommandLineCodeExecutor(
            image=self._image,
            container_name=self._container_name,
            timeout=self._timeout,
            work_dir=self._work_dir,
            extra_volumes=json.loads(self._extra_volumes.replace("'", '"')),
        )

        self._agent = CodeExecutorAgent(
            "PMCAExecutor",
            code_executor=self._executor,
            model_client_stream=True,
        )

        self._chinese_name = "代码执行助手"
        self._duty = """
        负责执行代码并反馈执行结果.
        """

    @property
    def agent(self):
        """The agent property."""
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value

    @property
    def executor(self):
        """The executor property."""
        return self._executor

    @executor.setter
    def executor(self, value):
        self._executor = value

    @property
    def duty(self):
        """The duty property."""
        return self._duty

    @duty.setter
    def duty(self, value):
        self._duty = value

    @property
    def chinese_name(self):
        """The _chinese_name property."""
        return self._chinese_name

    @chinese_name.setter
    def chinese_name(self, value):
        self._chinese_name = value
