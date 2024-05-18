import time
import json
import os
import subprocess

from jinja2 import Environment, BaseLoader

# from src.agents.patcher import Patcher

from src.llm import LLM
from src.state import AgentState
from src.project import ProjectManager
from src.services.utils import retry_wrapper, validate_responses

PROMPT = open("src/agents/ops/prompt.jinja2", "r").read().strip()
RERUNNER_PROMPT = open("src/agents/ops/rerunner.jinja2", "r").read().strip()
AGENT_NAME = "ops"

class Ops:
    def __init__(self, base_model: str):
        self.base_model = base_model
        self.llm = LLM(model_id=base_model)

    def render(
        self,
        conversation: str,
        system_os: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            conversation=conversation,
            system_os=system_os,
        )

    def render_rerunner(
        self,
        conversation: str,
        system_os: str,
        commands: list,
        error: str
    ):
        env = Environment(loader=BaseLoader())
        template = env.from_string(RERUNNER_PROMPT)
        return template.render(
            conversation=conversation,
            system_os=system_os,
            commands=commands,
            error=error
        )

    @validate_responses 
    def validate_response(self, response: str):
        if "commands" not in response:
            return False
        else:
            return response["commands"]
        
    @validate_responses    
    def validate_rerunner_response(self, response: str):
        if "action" not in response and "response" not in response:
            return False
        else:
            return response

    @retry_wrapper
    def run_code(
        self,
        commands: list,
        project_path: str,
        project_name: str,
        conversation: str,
        system_os: str
    ):  
        retries = 0
        print("here ", commands)
        for command in commands:
            command_failed = False
            process = self.exec_command(command, project_path)
            command_output = process.stdout.decode('utf-8')
            command_failed = process.returncode != 0
            print("here2 ", command_output, process.returncode)
            
            new_state = AgentState().new_state()
            new_state["internal_monologue"] = "Running code..."
            new_state["terminal_session"]["title"] = "Terminal"
            new_state["terminal_session"]["command"] = command
            new_state["terminal_session"]["output"] = command_output
            AgentState().add_to_current_state(project_name, new_state)
            time.sleep(1)

            if not command_failed:
                ProjectManager().add_message_from_devika(project_name, command_output)

            while command_failed and retries < 2:
                new_state = AgentState().new_state()
                print("here3 ", command_failed)
                new_state["internal_monologue"] = "Oh seems like there is some error... :("
                new_state["terminal_session"]["title"] = "Terminal"
                new_state["terminal_session"]["command"] = command
                new_state["terminal_session"]["output"] = command_output
                AgentState().add_to_current_state(project_name, new_state)
                time.sleep(1)
                
                prompt = self.render_rerunner(
                    conversation=conversation,
                    system_os=system_os,
                    commands=commands,
                    error=command_output
                )
                
                response = self.llm.inference(prompt, project_name, AGENT_NAME)
                print("here4 ", response)

                valid_response = self.validate_rerunner_response(response)
                
                print("here5 ", valid_response)
                if not valid_response:
                    return False
                
                action = valid_response["action"]
                
                command = valid_response["command"]
                response = valid_response["response"]
                
                ProjectManager().add_message_from_devika(project_name, response)
                
                command_failed = False
                process = self.exec_command(command, project_path)
                command_output = process.stdout.decode('utf-8')
                command_failed = process.returncode != 0
                
                if not command_failed:
                    ProjectManager().add_message_from_devika(project_name, command_output)

                new_state = AgentState().new_state()
                new_state["internal_monologue"] = "Running code..."
                new_state["terminal_session"]["title"] = "Terminal"
                new_state["terminal_session"]["command"] = command
                new_state["terminal_session"]["output"] = command_output
                AgentState().add_to_current_state(project_name, new_state)
                time.sleep(1)
                
                if command_failed:
                    retries += 1
                else:
                    break

        return True

    @retry_wrapper
    def execute(
        self,
        conversation: str,
        os_system: str,
        project_path: str,
        project_name: str
    ) -> str:
        prompt = self.render(conversation, os_system)
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)
        print("herex ", valid_response)
        self.run_code(
            valid_response,
            project_path,
            project_name,
            conversation,
            os_system
        )
        print("herex2 ", valid_response)
        return valid_response
    
    def exec_command(self, command: str, project_path: str):
        # command_set = str(command).split(" ")
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True, 
            cwd=project_path,
            timeout=300
        )
        return process