import time
from jinja2 import Environment, BaseLoader

from src.agents.formatter.formatter import Formatter
from src.agents.researcher.researcher import Researcher
from src.memory.chroma_db import ChromaDb
from src.llm import LLM
from src.state import AgentState
from src.project import ProjectManager
from src.services.utils import retry_wrapper, validate_responses
from src.common_util import convert_to_single_word, exec_command

PROMPT = open("src/agents/ops/prompt.jinja2", "r").read().strip()
RERUNNER_PROMPT = open("src/agents/ops/rerunner.jinja2", "r").read().strip()
AGENT_NAME = "ops"

class Ops:
    def __init__(self, base_model: str, chroma_db : ChromaDb):
        self.base_model = base_model
        self.llm = LLM(model_id=base_model)
        self.chroma_db = chroma_db

    def render(
        self,
        conversation: list,
        knowledge: str,
        system_os: str
    ) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            conversation=conversation,
            knowledge=knowledge,
            system_os=system_os,
        )

    def render_rerunner(
        self,
        conversation: list,
        knowledge: str,
        system_os: str,
        commands: list,
        command: str,
        error: str
    ):
        env = Environment(loader=BaseLoader())
        template = env.from_string(RERUNNER_PROMPT)
        return template.render(
            conversation=conversation,
            knowledge=knowledge,
            system_os=system_os,
            commands=commands,
            command=command,
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
        knowledge: str,
        system_os: str,
        search_engine: str
    ):  
        retries = 0
        commands_excecuted = []
        for command in commands:
            command_failed = False
            returncode, command_output, cleaned_output = exec_command(command, project_path)
            command_failed = returncode != 0
            
            self.update_terminal_sessiom(command, command_output, project_name)

            ProjectManager().add_message_from_devika(project_name, self.format_command_output(cleaned_output))

            while command_failed and retries < 2:
                print("Command failed, retrying...")
                command_failed, command, returncode, command_output, cleaned_output = self.rerunner(commands, command, cleaned_output, project_path, project_name, conversation, knowledge, system_os)
                
                if command_failed:
                    retries += 1

            if command_failed:
                ProjectManager().add_message_from_devika(project_name, "Getting researcher help")
                search_results = self.research_issue(commands, command, command_output, project_name, ProjectManager(), AgentState(), search_engine, Formatter(base_model=self.base_model))
                command_failed, command, returncode, command_output, cleaned_output = self.rerunner(commands, command, cleaned_output, project_path, project_name, conversation, search_results, system_os)

            if command_failed:
                ProjectManager().add_message_from_devika(project_name, "command execution is failed! Sorry! I'm out of ideas. Please try with different model and/or search engine")
                break
            else:
                ProjectManager().add_message_from_devika(project_name, "command executed successfully!")
                commands_excecuted.append(command)
        
        if len(commands_excecuted) == len(commands):
            ProjectManager().add_message_from_devika(project_name, "All commands executed successfully!")
            self.chroma_db.add_knowledge(conversation[-1], commands_excecuted)
        AgentState().set_agent_active(project_name, False)
        AgentState().set_agent_completed(project_name, True)
        
        return True

    @retry_wrapper
    def execute(
        self,
        conversation: list,
        os_system: str,
        project_path: str,
        project_name: str,
        search_engine: str
    ) -> str:
        knowledge = self.chroma_db.query(conversation[-1])
        prompt = self.render(conversation, knowledge, os_system)
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)
        self.run_code(
            valid_response,
            project_path,
            project_name,
            conversation,
            knowledge,
            os_system,
            search_engine
        )
        return valid_response

    def research_issue(self, commands: list, command: str, command_output: str, project_name: str, project_manager: ProjectManager, agent_state: AgentState, engine: str, formatter: Formatter) -> str:
        researcher = Researcher(base_model=self.base_model)
        research_response = researcher.execute_ops(commands, command, command_output, [], project_name=project_name)
        print("\nOps research_response :: ", research_response)

        search_results, ask_user_prompt = researcher.search(research_response, project_name, project_manager, agent_state, engine, formatter)

        return search_results


    def rerunner(self,
        commands: list,
        command:str,
        error:str,
        project_path: str,
        project_name: str,
        conversation: list,
        knowledge: str,
        system_os: str):

        self.update_terminal_sessiom(command, error, project_name)
        
        prompt = self.render_rerunner(
            conversation=conversation,
            knowledge=knowledge,
            system_os=system_os,
            commands=commands,
            command=command,
            error=error
        )
        
        response = self.llm.inference(prompt, project_name, AGENT_NAME)

        valid_response = self.validate_rerunner_response(response)
        
        if not valid_response:
            return False
        
        action = valid_response["action"]
        
        command = valid_response["command"]
        response = valid_response["response"]
        
        ProjectManager().add_message_from_devika(project_name, "<rerun response>")
        
        command_failed = False
        returncode, command_output, cleaned_output = exec_command(command, project_path)
        command_failed = returncode != 0
        
        ProjectManager().add_message_from_devika(project_name, self.format_command_output(cleaned_output))

        self.update_terminal_sessiom(command, command_output, project_name)
        
        return command_failed, command, returncode, command_output, cleaned_output

    def update_terminal_sessiom(self, command, command_output, project_name):
        new_state = AgentState().new_state()
        new_state["internal_monologue"] = "Running code..."
        new_state["terminal_session"]["title"] = "Terminal"
        new_state["terminal_session"]["command"] = command
        new_state["terminal_session"]["output"] = command_output
        AgentState().add_to_current_state(project_name, new_state)
        time.sleep(1)

    def format_command_output(self, command_output: str):
        command_output = command_output
        return command_output