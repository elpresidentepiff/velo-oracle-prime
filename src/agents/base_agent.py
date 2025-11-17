"""
VÉLØ Oracle - Multi-Agent Architecture Base Classes

Inspired by MetaGPT's "Software Company as Multi-Agent System" paradigm.

Each agent has a specialized role:
- Analyst Agent: Runs SQPE, TIE, NDS modules
- Risk Agent: Kelly Criterion, bankroll management
- Execution Agent: Betfair API interaction
- Learning Agent: Post-race evaluation, retraining
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Inter-agent communication message."""
    sender: str
    receiver: str
    content: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_type: str = "info"  # info, request, response, command


@dataclass
class AgentState:
    """Current state of an agent."""
    agent_name: str
    status: str  # idle, working, waiting, error
    current_task: Optional[str] = None
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Abstract base class for all VÉLØ agents.
    
    Agents are autonomous entities with specialized roles that collaborate
    to achieve the overall goal of profitable betting.
    """
    
    def __init__(self, name: str, role: str):
        """
        Initialize agent.
        
        Args:
            name: Unique identifier for this agent
            role: Description of agent's role/responsibility
        """
        self.name = name
        self.role = role
        self.state = AgentState(agent_name=name, status="idle")
        self.message_queue: List[Message] = []
        self.logger = logging.getLogger(f"Agent.{name}")
        
        self.logger.info(f"Agent initialized: {name} ({role})")
    
    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process input data and return results.
        
        This is the main work method that each agent must implement.
        
        Args:
            input_data: Input data specific to the agent's role
            
        Returns:
            Dict containing the agent's output
        """
        pass
    
    def receive_message(self, message: Message):
        """
        Receive a message from another agent.
        
        Args:
            message: Message object from another agent
        """
        self.logger.debug(f"Received message from {message.sender}: {message.message_type}")
        self.message_queue.append(message)
    
    def send_message(self, receiver: str, content: Dict[str, Any], message_type: str = "info") -> Message:
        """
        Send a message to another agent.
        
        Args:
            receiver: Name of the receiving agent
            content: Message content
            message_type: Type of message
            
        Returns:
            The sent message
        """
        message = Message(
            sender=self.name,
            receiver=receiver,
            content=content,
            message_type=message_type
        )
        self.logger.debug(f"Sent message to {receiver}: {message_type}")
        return message
    
    def update_state(self, status: str, task: Optional[str] = None, **metadata):
        """
        Update agent's current state.
        
        Args:
            status: New status
            task: Current task description
            **metadata: Additional state metadata
        """
        self.state.status = status
        self.state.current_task = task
        self.state.last_update = datetime.now().isoformat()
        self.state.metadata.update(metadata)
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', role='{self.role}', status='{self.state.status}')"


class AgentOrchestrator:
    """
    Orchestrates communication and workflow between agents.
    
    This is a lightweight coordinator that doesn't make decisions,
    but ensures agents work together smoothly.
    """
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.agents: Dict[str, BaseAgent] = {}
        self.message_log: List[Message] = []
        self.logger = logging.getLogger("AgentOrchestrator")
        
        self.logger.info("Agent Orchestrator initialized")
    
    def register_agent(self, agent: BaseAgent):
        """
        Register an agent with the orchestrator.
        
        Args:
            agent: Agent instance to register
        """
        self.agents[agent.name] = agent
        self.logger.info(f"Registered agent: {agent.name} ({agent.role})")
    
    def route_message(self, message: Message):
        """
        Route a message from one agent to another.
        
        Args:
            message: Message to route
        """
        if message.receiver not in self.agents:
            self.logger.error(f"Unknown receiver: {message.receiver}")
            return
        
        receiver_agent = self.agents[message.receiver]
        receiver_agent.receive_message(message)
        self.message_log.append(message)
        
        self.logger.debug(f"Routed message: {message.sender} -> {message.receiver}")
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """
        Get an agent by name.
        
        Args:
            name: Agent name
            
        Returns:
            Agent instance or None
        """
        return self.agents.get(name)
    
    def get_all_states(self) -> Dict[str, AgentState]:
        """Get current state of all agents."""
        return {name: agent.get_state() for name, agent in self.agents.items()}
    
    def execute_workflow(self, workflow: List[str], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a workflow by running agents in sequence.
        
        Args:
            workflow: List of agent names in execution order
            input_data: Initial input data
            
        Returns:
            Final output from the workflow
        """
        self.logger.info(f"Executing workflow: {' -> '.join(workflow)}")
        
        current_data = input_data
        
        for agent_name in workflow:
            agent = self.get_agent(agent_name)
            if not agent:
                self.logger.error(f"Agent not found in workflow: {agent_name}")
                continue
            
            self.logger.info(f"Processing: {agent_name}")
            agent.update_state("working", task=f"Workflow step")
            
            try:
                current_data = agent.process(current_data)
                agent.update_state("idle")
            except Exception as e:
                self.logger.error(f"Agent {agent_name} failed: {e}")
                agent.update_state("error", task=str(e))
                raise
        
        self.logger.info("Workflow complete")
        return current_data

