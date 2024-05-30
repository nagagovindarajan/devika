from jinja2 import Environment, BaseLoader
import re
from src.llm import LLM

PROMPT = open("src/agents/formatter/prompt.jinja2").read().strip()
AGENT_NAME = "formatter"

class Formatter:
    def __init__(self, base_model: str):
        self.llm = LLM(model_id=base_model)

    def render(self, raw_text: str, formatter_name:str = None) -> str:
        env = Environment(loader=BaseLoader())
        prompt_template = PROMPT
        if formatter_name:
            prompt_template = open("src/agents/formatter/"+formatter_name+".jinja2").read().strip()
        template = env.from_string(prompt_template)
        return template.render(raw_text=raw_text)
    
    def validate_response(self, response: str) -> bool:
        return True

    def execute(self, raw_text: str, project_name: str, formatter_name:str = None):
        raw_text = self.render(raw_text, formatter_name)
        response = self.llm.inference(raw_text, project_name, AGENT_NAME)
        formatted_response, response_type = self.cleaned_response(response, formatter_name)
        return formatted_response, response_type
    
    def cleaned_response(self, response: str, formatter_name: str):
        response_type = "html"
        final_response = response
        if formatter_name == "html_table_formatter":
            pattern = r'<html_table>(.*?)</html_table>'
            match = re.search(pattern, response, re.DOTALL)
            if match:
                final_response = match.group(1)
        elif formatter_name == "chart_data_formatter":
            output_pattern = r'<output>(.*?)</output>'
            output_match = re.search(output_pattern, response, re.DOTALL)
            if output_match:
                final_response = output_match.group(1)
            chart_type_pattern = r'<chart_type>(.*?)</chart_type>'
            chart_type_match = re.search(chart_type_pattern, response, re.DOTALL)
            if chart_type_match:
                response_type = chart_type_match.group(1)
                print("response_typX1 ", response_type)
            
        print("response_typX2 ", response_type)
        return final_response, response_type
