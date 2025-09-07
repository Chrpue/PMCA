from autogen_agentchat.agents import UserProxyAgent


class PMCAUser:
    def __init__(self):
        self._name = "PMCAUserProxy"
        self._description = "一个用户代理，当需要让用户决定任务后续应该如何执行，或者需要用户给予建议的时候启用"
        self._input_func = lambda _: input("\n请输入本次任务 > ").strip()
        self._chinese_name = "用户代理"
        self._agent = UserProxyAgent(
            self._name,
            description=self._description,
            input_func=self._input_func,
        )

        self._duty = """
    1. 给予用户意见或提供信息.
    2. 参与决策
    """

    @property
    def agent(self):
        """The agent property."""
        return self._agent

    @agent.setter
    def agent(self, value):
        self._agent = value

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

    @property
    def name(self):
        """The name property."""
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
