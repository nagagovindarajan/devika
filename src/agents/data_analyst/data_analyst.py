from datetime import datetime
import time
import json
from jinja2 import Environment, BaseLoader

from src.agents.formatter.formatter import Formatter
from src.agents.researcher.researcher import Researcher
from src.memory.chroma_db import ChromaDb
from src.llm import LLM
from src.state import AgentState
from src.project import ProjectManager
from src.services.utils import retry_wrapper, validate_responses
from src.common_util import exec_command, is_json

PROMPT = open("src/agents/data_analyst/prompt.jinja2", "r").read().strip()
AGENT_NAME = "data_analyst"

class DataAnalyst:
    def __init__(self, base_model: str, chroma_db : ChromaDb):
        self.base_model = base_model
        self.llm = LLM(model_id=base_model)
        self.chroma_db = chroma_db

    def render(
        self,
        user_request: str,
        csv_content: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            USER_REQUEST=user_request,
            CSV_CONTENT=csv_content
        )
 
    @retry_wrapper
    def execute(
        self,
        conversation: list,
        os_system: str,
        project_path: str,
        project_name: str,
        search_engine: str
    ) -> str:
        # knowledge = self.chroma_db.query(conversation[-1])
        query = conversation[-1]
        content = self.chroma_db.get_text_content("/Users/nagagovindar@sphnet.com.sg/Documents/my_projects/devika/data/csv/SuperMarket-Analysis.csv")
        prompt = self.render(query, content)
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        AgentState().set_agent_active(project_name, False)
        if self.validate_response(response):
            return response
        return "Invalid response"
    
    def validate_response(self, response: str) -> bool:
        if ("<analysis>" in response and
            "<data_summary>" in response and
            "<findings>" in response and
            "<conclusion>" in response):
            return True
        return False
    

