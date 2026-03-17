from abc import ABC, abstractmethod
from typing import Optional, Any
import asyncio
from datetime import datetime
import uuid

from ..models.schemas import AgentMessage
from ..memory.vector_store import VectorMemory


class BaseAgent(ABC):
    def __init__(
        self,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        memory: Optional[VectorMemory] = None,
        llm: Optional[Any] = None,
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.name = name or self.__class__.__name__
        self.memory = memory
        self.llm = llm
        self.message_queue: list[AgentMessage] = []
        self.is_running = False

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        pass

    def send_message(self, recipient: str, message_type: str, content: dict):
        message = AgentMessage(
            sender=self.name,
            recipient=recipient,
            message_type=message_type,
            content=content,
            timestamp=datetime.now(),
        )
        self.message_queue.append(message)

    def receive_message(self, message: AgentMessage):
        self.message_queue.append(message)

    def get_pending_messages(self) -> list[AgentMessage]:
        messages = self.message_queue.copy()
        self.message_queue.clear()
        return messages

    async def run(self, input_data: Any) -> Any:
        self.is_running = True
        try:
            result = await self.process(input_data)
            return result
        finally:
            self.is_running = False


class AgentOrchestrator:
    def __init__(self, memory: Optional[VectorMemory] = None, llm: Optional[Any] = None):
        self.agents: dict[str, BaseAgent] = {}
        self.message_bus: list[AgentMessage] = []
        self.memory = memory or VectorMemory()
        self.llm = llm
        self.is_running = False

    def register_agent(self, agent: BaseAgent):
        if not agent.memory:
            agent.memory = self.memory
        if not agent.llm:
            agent.llm = self.llm
        self.agents[agent.name] = agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.agents.get(name)

    def broadcast_message(self, message: AgentMessage, exclude: Optional[list[str]] = None):
        exclude = exclude or []
        for agent_name, agent in self.agents.items():
            if agent_name not in exclude:
                agent.receive_message(message)
        self.message_bus.append(message)

    def route_message(self, message: AgentMessage):
        recipient = self.agents.get(message.recipient)
        if recipient:
            recipient.receive_message(message)
        else:
            self.broadcast_message(message, exclude=[message.sender])

    async def run_pipeline(self, initial_input: Any, pipeline: list[str]) -> dict:
        self.is_running = True
        results = {}
        current_data = initial_input

        try:
            for agent_name in pipeline:
                agent = self.get_agent(agent_name)
                if not agent:
                    raise ValueError(f"Agent {agent_name} not found")

                result = await agent.process(current_data)
                results[agent_name] = result

                for message in agent.get_pending_messages():
                    self.route_message(message)

                current_data = result

            return results
        finally:
            self.is_running = False

    async def run_concurrent(
        self, initial_input: Any, agent_names: list[str]
    ) -> dict[str, Any]:
        self.is_running = True
        try:
            tasks = []
            for agent_name in agent_names:
                agent = self.get_agent(agent_name)
                if agent:
                    tasks.append(agent.process(initial_input))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            output = {}
            for i, agent_name in enumerate(agent_names):
                if i < len(results):
                    output[agent_name] = results[i]

            for agent in self.agents.values():
                for message in agent.get_pending_messages():
                    self.route_message(message)

            return output
        finally:
            self.is_running = False

    async def process_all_messages(self):
        while any(agent.message_queue for agent in self.agents.values()):
            for agent in self.agents.values():
                messages = agent.get_pending_messages()
                for message in messages:
                    self.route_message(message)
            await asyncio.sleep(0.1)
