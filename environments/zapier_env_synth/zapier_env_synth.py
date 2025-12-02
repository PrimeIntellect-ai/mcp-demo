"""
Synthetic Zapier Environment for vf-eval

Usage:
    uv run vf-eval zapier-env-synth -n 1 -r 1 -m <model> -b <base_url>
"""

import json
from typing import Dict, Callable, Optional, Any
from dataclasses import dataclass
from datasets import Dataset

import verifiers as vf
from verifiers import Messages, State


# =============================================================================
# Synthetic Transport (replaces real MCP connection)
# =============================================================================

@dataclass
class Tool:
    """Minimal Tool definition matching MCP's Tool type."""
    name: str
    description: str
    inputSchema: dict


class SyntheticTransport:
    """Mock MCP transport that routes tool calls to in-memory handlers."""
    
    def __init__(
        self,
        tools: Dict[str, Tool],
        handlers: Dict[str, Callable[[dict, dict], str]],
        data: Optional[dict] = None,
    ):
        self._tools = tools
        self.handlers = handlers
        self.data = data if data is not None else {}
        self._connected = False
    
    @property
    def tools(self) -> Dict[str, Tool]:
        return self._tools
    
    async def connect(self) -> Dict[str, Tool]:
        self._connected = True
        return self._tools
    
    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name not in self.handlers:
            raise ValueError(f"No handler for tool: {tool_name}")
        result = self.handlers[tool_name](self.data, arguments)
        return str(result)
    
    async def disconnect(self) -> None:
        self._connected = False
    
    async def is_connected(self) -> bool:
        return self._connected


# =============================================================================
# Synthetic Airtable Backend
# =============================================================================

class SyntheticAirtable:
    """In-memory Airtable-like database."""
    
    def __init__(self):
        self.data: Dict[str, list] = {}
        self._id_counter = 0
    
    def add_table(self, name: str, records: list):
        for record in records:
            if "id" not in record:
                self._id_counter += 1
                record["id"] = f"rec{self._id_counter}"
        self.data[name] = records
    
    def get_tools(self) -> Dict[str, Tool]:
        return {
            "list_records": Tool(
                name="list_records",
                description="List all records in a table. Returns records and total count.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Name of the table"},
                        "max_records": {"type": "integer", "description": "Max records to return"},
                    },
                    "required": ["table_name"]
                }
            ),
            "search_records": Tool(
                name="search_records",
                description="Search for records matching a query string across all fields.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Name of the table"},
                        "query": {"type": "string", "description": "Search query"},
                        "field": {"type": "string", "description": "Specific field to search"},
                    },
                    "required": ["table_name", "query"]
                }
            ),
            "count_records": Tool(
                name="count_records",
                description="Count total records in a table.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Name of the table"},
                    },
                    "required": ["table_name"]
                }
            ),
            "get_record": Tool(
                name="get_record",
                description="Get a specific record by ID.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string", "description": "Name of the table"},
                        "record_id": {"type": "string", "description": "Record ID"},
                    },
                    "required": ["table_name", "record_id"]
                }
            ),
        }
    
    def get_handlers(self) -> Dict[str, Callable]:
        def list_records(data, args):
            table = args.get("table_name")
            max_recs = args.get("max_records")
            if table not in data:
                return json.dumps({"error": f"Table '{table}' not found"})
            records = data[table][:max_recs] if max_recs else data[table]
            return json.dumps({"records": records, "total": len(data[table])})
        
        def search_records(data, args):
            table = args.get("table_name")
            query = args.get("query", "").lower()
            field = args.get("field")
            if table not in data:
                return json.dumps({"error": f"Table '{table}' not found"})
            results = []
            for rec in data[table]:
                if field:
                    if query in str(rec.get(field, "")).lower():
                        results.append(rec)
                else:
                    if any(query in str(v).lower() for v in rec.values()):
                        results.append(rec)
            return json.dumps({"records": results, "count": len(results)})
        
        def count_records(data, args):
            table = args.get("table_name")
            if table not in data:
                return json.dumps({"error": f"Table '{table}' not found"})
            return json.dumps({"count": len(data[table])})
        
        def get_record(data, args):
            table = args.get("table_name")
            record_id = args.get("record_id")
            if table not in data:
                return json.dumps({"error": f"Table '{table}' not found"})
            for rec in data[table]:
                if rec.get("id") == record_id:
                    return json.dumps({"record": rec})
            return json.dumps({"error": f"Record '{record_id}' not found"})
        
        return {
            "list_records": list_records,
            "search_records": search_records,
            "count_records": count_records,
            "get_record": get_record,
        }


# =============================================================================
# Tool Wrapper (for OpenAI-style tool definitions)
# =============================================================================

class SyntheticToolWrapper:
    """Wraps a synthetic tool to work with verifiers ToolEnv."""
    
    def __init__(self, tool: Tool, transport: SyntheticTransport):
        self.tool = tool
        self.transport = transport
        self.__name__ = tool.name
        self.__doc__ = tool.description
        self.__annotations__ = self._build_annotations()
    
    def _build_annotations(self) -> dict:
        annotations = {}
        if self.tool.inputSchema:
            props = self.tool.inputSchema.get("properties", {})
            for name, spec in props.items():
                ptype = spec.get("type", "string")
                annotations[name] = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}.get(ptype, Any)
        annotations["return"] = str
        return annotations
    
    async def __call__(self, **kwargs):
        return await self.transport.call_tool(self.tool.name, kwargs)
    
    def to_oai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.__name__,
                "description": self.__doc__ or "",
                "parameters": self.tool.inputSchema or {"type": "object", "properties": {}},
            },
        }


# =============================================================================
# Synthetic MCP Environment
# =============================================================================

class SyntheticMCPEnv(vf.ToolEnv):
    """
    A ToolEnv that uses synthetic backends instead of real MCP connections.
    """
    
    def __init__(
        self,
        synthetic_backend: SyntheticAirtable,
        max_turns: int = 10,
        **kwargs
    ):
        self.synthetic_backend = synthetic_backend
        self.transport: Optional[SyntheticTransport] = None
        
        # Initialize parent with empty tools (we'll add them in setup)
        super().__init__(
            tools=[],
            max_turns=max_turns,
            **kwargs
        )
    
    async def _ensure_transport(self):
        """Create and connect transport if not already done."""
        if self.transport is None:
            self.transport = SyntheticTransport(
                tools=self.synthetic_backend.get_tools(),
                handlers=self.synthetic_backend.get_handlers(),
                data=self.synthetic_backend.data
            )
            await self.transport.connect()
            
            # Register tools
            self.tools = []
            self.oai_tools = []
            self.tool_map = {}
            
            for tool in self.transport.tools.values():
                wrapper = SyntheticToolWrapper(tool, self.transport)
                self.tools.append(wrapper)
                self.oai_tools.append(wrapper.to_oai_tool())
                self.tool_map[wrapper.__name__] = wrapper
    
    async def setup_state(self, state: State, **kwargs) -> State:
        """Set up state and ensure transport is connected."""
        await self._ensure_transport()
        state = await super().setup_state(state, **kwargs)
        if self.oai_tools:
            state["info"]["oai_tools"] = self.oai_tools
        return state


# =============================================================================
# Synthetic Data
# =============================================================================

SYNTHETIC_CANDIDATES = [
    {"Name": "Alice Johnson", "Email": "alice@example.com", "Status": "Active", "Role": "Senior Engineer", "Experience_Years": 5},
    {"Name": "Bob Smith", "Email": "bob@example.com", "Status": "Interviewing", "Role": "Product Designer", "Experience_Years": 3},
    {"Name": "Carol Williams", "Email": "carol@example.com", "Status": "Active", "Role": "Product Manager", "Experience_Years": 7},
    {"Name": "David Brown", "Email": "david@example.com", "Status": "Rejected", "Role": "Junior Engineer", "Experience_Years": 1},
    {"Name": "Eve Davis", "Email": "eve@example.com", "Status": "Active", "Role": "Data Scientist", "Experience_Years": 4},
    {"Name": "Frank Miller", "Email": "frank@example.com", "Status": "Offer Extended", "Role": "Senior Engineer", "Experience_Years": 8},
]


# =============================================================================
# Judge Reward Function
# =============================================================================

async def judge_reward(judge, prompt, completion, answer, state):
    judge_response = await judge(prompt, completion, answer, state)
    return 1.0 if "yes" in judge_response.lower() else 0.0


# =============================================================================
# Load Environment (required for vf-eval)
# =============================================================================

def load_environment(**kwargs):
    """Load the synthetic Zapier environment."""
    
    # Create synthetic backend
    airtable = SyntheticAirtable()
    airtable.add_table("candidates", SYNTHETIC_CANDIDATES)
    
    # Create dataset
    ds = Dataset.from_dict({
        "question": [
            "How many candidates do we have currently?",
            "How many active candidates are there?",
            "Who are the senior engineers?",
        ],
        "answer": [
            "6",
            "3", 
            "Alice Johnson and Frank Miller",
        ],
    })
    
    # Create rubric
    rub = vf.JudgeRubric(judge_model="gpt-4.1-mini")
    rub.add_reward_func(judge_reward, weight=1.0)
    
    # Create and return environment
    env = SyntheticMCPEnv(
        synthetic_backend=airtable,
        dataset=ds,
        rubric=rub,
        max_turns=10,
    )
    
    return env
