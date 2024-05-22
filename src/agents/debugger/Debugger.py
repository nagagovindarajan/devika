import time
import json
import os
import subprocess
import re

from jinja2 import Environment, BaseLoader

from src.agents.formatter.formatter import Formatter
from src.agents.researcher.researcher import Researcher
from src.agents.patcher import Patcher

from src.llm import LLM
from src.state import AgentState
from src.project import ProjectManager
from src.services.utils import retry_wrapper, validate_responses
from src.common_util import exec_command

PROMPT = open("src/agents/debugger/prompt.jinja2", "r").read().strip()
RERUNNER_PROMPT = open("src/agents/debugger/rerunner.jinja2", "r").read().strip()
AGENT_NAME = "debugger"

class Debugger:
    def __init__(self, base_model: str):
        self.base_model = base_model
        self.llm = LLM(model_id=base_model)

    def render(
        self,
        conversation: str,
        code_markdown: str,
        system_os: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            conversation=conversation,
            code_markdown=code_markdown,
            system_os=system_os,
        )

    def render_rerunner(
        self,
        conversation: str,
        code_markdown: str,
        system_os: str,
        commands: list,
        error: str
    ):
        env = Environment(loader=BaseLoader())
        template = env.from_string(RERUNNER_PROMPT)
        return template.render(
            conversation=conversation,
            code_markdown=code_markdown,
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
        conversation: list,
        code_markdown: str,
        system_os: str,
        search_engine: str
    ):  
        retries = 0
        commands = ["terraform init", "terraform validate", "terraform plan"]

        for command in commands:
            command_failed = False
            ProjectManager().add_message_from_devika(project_name, "Exeuting command: "+command)
            returncode, command_output, cleaned_output = exec_command(command, project_path)
            command_failed = returncode != 0
            
            new_state = AgentState().new_state()
            new_state["internal_monologue"] = "Running code..."
            new_state["terminal_session"]["title"] = "Terminal"
            new_state["terminal_session"]["command"] = command
            new_state["terminal_session"]["output"] = command_output
            AgentState().add_to_current_state(project_name, new_state)
            time.sleep(1)

            if not command_failed:
                ProjectManager().add_message_from_devika(project_name, f"Command executed successfully\n{cleaned_output}")

            while command_failed and retries < 2:
                new_state = AgentState().new_state()
                new_state["internal_monologue"] = "Oh seems like there is some error... :("
                new_state["terminal_session"]["title"] = "Terminal"
                new_state["terminal_session"]["command"] = command
                new_state["terminal_session"]["output"] = command_output
                AgentState().add_to_current_state(project_name, new_state)
                time.sleep(1)
                
                prompt = self.render_rerunner(
                    conversation=conversation,
                    code_markdown=code_markdown,
                    system_os=system_os,
                    commands=[command],
                    error=cleaned_output
                )
                
                response = self.llm.inference(prompt, project_name, AGENT_NAME)
                
                valid_response = self.validate_rerunner_response(response)
                
                if not valid_response:
                    return False
                
                action = valid_response["action"]
                
                if action == "command":
                    command = valid_response["command"]
                    response = valid_response["response"]
                    
                    ProjectManager().add_message_from_devika(project_name, response)
                    
                    command_failed = False
                    
                    returncode, command_output, cleaned_output = exec_command(command, project_path)
                    command_failed = returncode != 0
                    
                    new_state = AgentState().new_state()
                    new_state["internal_monologue"] = "Running code..."
                    new_state["terminal_session"]["title"] = "Terminal"
                    new_state["terminal_session"]["command"] = command
                    new_state["terminal_session"]["output"] = command_output
                    AgentState().add_to_current_state(project_name, new_state)
                    time.sleep(1)
                    
                    ProjectManager().add_message_from_devika(project_name, cleaned_output)

                    if command_failed:
                        retries += 1
                    else:
                        break
                elif action == "patch":
                    response = valid_response["response"]
                    
                    ProjectManager().add_message_from_devika(project_name, response)
                    
                    code = Patcher(base_model=self.base_model).execute(
                        conversation=conversation,
                        code_markdown=code_markdown,
                        commands=commands,
                        error=cleaned_output,
                        user_context = "",
                        search_results= {},
                        system_os=system_os,
                        project_name=project_name
                    )
                    
                    Patcher(base_model=self.base_model).save_code_to_project(code, project_name)
                    
                    command_failed = False
                    
                    returncode, command_output, cleaned_output = exec_command(command, project_path)
                    command_failed = returncode != 0
                    
                    new_state = AgentState().new_state()
                    new_state["internal_monologue"] = "Running code..."
                    new_state["terminal_session"]["title"] = "Terminal"
                    new_state["terminal_session"]["command"] = command
                    new_state["terminal_session"]["output"] = command_output
                    AgentState().add_to_current_state(project_name, new_state)
                    time.sleep(1)
                    ProjectManager().add_message_from_devika(project_name, cleaned_output)

                    if command_failed:
                        retries += 1
                    else:
                        break

            if command_failed:
                ProjectManager().add_message_from_devika(project_name, "Getting researcher help")
                self.research_issue(
                    conversation=conversation,
                    code_markdown=code_markdown,
                    system_os=system_os,
                    command=command,
                    command_output=cleaned_output,
                    project_name=project_name,
                    project_manager=ProjectManager(),
                    agent_state=AgentState(),
                    engine=search_engine,
                    formatter=Formatter(base_model=self.base_model),
                    patcher=Patcher(base_model=self.base_model)
                )                

                ProjectManager().add_message_from_devika(project_name, "Researcher updated the code. Let's run now.")

                command_failed = False
                    
                returncode, command_output, cleaned_output = exec_command(command, project_path)
                command_failed = returncode != 0
                
                new_state = AgentState().new_state()
                new_state["internal_monologue"] = "Running code..."
                new_state["terminal_session"]["title"] = "Terminal"
                new_state["terminal_session"]["command"] = command
                new_state["terminal_session"]["output"] = command_output
                AgentState().add_to_current_state(project_name, new_state)
                time.sleep(1)
                ProjectManager().add_message_from_devika(project_name, cleaned_output)

                if command_failed:
                    ProjectManager().add_message_from_devika(project_name, "Sorry I could not fix it. Please try with different model or different search engine.")
                    break

        ProjectManager().add_message_from_devika(project_name, "Code ran successfully.")
        AgentState().set_agent_active(project_name, False)
        AgentState().set_agent_completed(project_name, True)

        return True

    @retry_wrapper
    def execute(
        self,
        conversation: list,
        code_markdown: str,
        os_system: str,
        project_path: str,
        project_name: str,
        search_engine: str
    ) -> str:
        prompt = self.render(conversation, code_markdown, os_system)
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)

        self.run_code(
            valid_response,
            project_path,
            project_name,
            conversation,
            code_markdown,
            os_system,
            search_engine
        )
        return valid_response
    
    def research_issue(self, conversation: list, code_markdown: str, system_os: str, command: str, command_output: str, project_name: str, project_manager: ProjectManager, agent_state: AgentState, engine: str, formatter: Formatter, patcher: Patcher) -> bool:
        researcher = Researcher(base_model=self.base_model)
        research_response = researcher.execute_debug(code_markdown, command, command_output, [], project_name=project_name)
        print("\research_response :: ", research_response, '\n')

        search_results, ask_user_prompt = researcher.search(research_response, project_name, project_manager, agent_state, engine, formatter)

        code = patcher.execute(
                conversation=conversation,
                code_markdown=code_markdown,
                commands=[command],
                error=command_output,
                user_context = ask_user_prompt,
                search_results= search_results,
                system_os=system_os,
                project_name=project_name
            )
        
        print("\ncode :: ", code, '\n')

        patcher.save_code_to_project(code, project_name)

        agent_state.set_agent_active(project_name, False)

        return True