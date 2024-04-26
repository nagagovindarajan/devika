import json

from jinja2 import Environment, BaseLoader

from src.services.utils import retry_wrapper
from src.llm import LLM

PROMPT = open("src/agents/decision/prompt.jinja2").read().strip()
AGENT_NAME = "decision"

class Decision:
    def __init__(self, base_model: str):
        self.llm = LLM(model_id=base_model)

    def render(self, prompt: str) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(prompt=prompt)

    def validate_response(self, response: str):
        response = response.strip().replace("```json", "```")
        
        if response.startswith("```") and response.endswith("```"):
            response = response[3:-3].strip()

        try:
            response = json.loads(response)
        except Exception as _:
            return False
        
        for item in response:
            if "function" not in item or "args" not in item or "reply" not in item:
                return False
        
        return response

    @retry_wrapper
    def execute(self, prompt: str, project_name: str) -> str:
        rendered_prompt = self.render(prompt)
        response = self.llm.inference(rendered_prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)

        return valid_response