import json
from typing import List

from jinja2 import Environment, BaseLoader

from src.agents.formatter.formatter import Formatter
from src.browser.browser import Browser
from src.project import ProjectManager
from src.llm import LLM
from src.services.utils import retry_wrapper, validate_responses
from src.browser.search import BingSearch, DuckDuckGoSearch, GoogleSearch
import time
import asyncio

from src.logger import Logger
from src.state import AgentState
from src.socket_instance import emit_agent

logger = Logger()

PROMPT = open("src/agents/researcher/prompt.jinja2").read().strip()
DEBUG_PROMPT = open("src/agents/researcher/prompt_debug.jinja2").read().strip()
AGENT_NAME = "reseacher"

class Researcher:
    def __init__(self, base_model: str):
        self.bing_search = BingSearch()
        self.llm = LLM(model_id=base_model)

    def render(self, step_by_step_plan: str, contextual_keywords: str) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(PROMPT)
        return template.render(
            step_by_step_plan=step_by_step_plan,
            contextual_keywords=contextual_keywords
        )
    
    def render_debug(self, code_markdown: str, command: str, error: str, contextual_keywords: str) -> str:
        env = Environment(loader=BaseLoader())
        template = env.from_string(DEBUG_PROMPT)
        return template.render(
            code_markdown=code_markdown,
            command=command,
            error=error,
            contextual_keywords=contextual_keywords
        )

    @validate_responses
    def validate_response(self, response: str) -> dict | bool:

        if "queries" not in response and "ask_user" not in response:
            return False
        else:
            return {
                "queries": response["queries"],
                "ask_user": response["ask_user"]
            }

    @retry_wrapper
    def execute(self, step_by_step_plan: str, contextual_keywords: List[str], project_name: str) -> dict | bool:
        contextual_keywords_str = ", ".join(map(lambda k: k.capitalize(), contextual_keywords))
        prompt = self.render(step_by_step_plan, contextual_keywords_str)
        
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)

        return valid_response

    @retry_wrapper
    def execute_debug(self, code_markdown: str, command: str, error: str, contextual_keywords: List[str], project_name: str) -> dict | bool:
        contextual_keywords_str = ", ".join(map(lambda k: k.capitalize(), contextual_keywords))
        prompt = self.render_debug(code_markdown, command, error, contextual_keywords_str)
        
        response = self.llm.inference(prompt, project_name, AGENT_NAME)
        
        valid_response = self.validate_response(response)

        return valid_response
    
    def search(self, research_response, project_name: str, project_manager: ProjectManager, agent_state: AgentState, engine: str, formatter: Formatter) -> List[str]:

        queries = research_response["queries"]
        queries_combined = ", ".join(queries)
        ask_user = research_response["ask_user"]

        if (queries and len(queries) > 0) or ask_user != "":
            project_manager.add_message_from_devika(
                project_name,
                f"I am browsing the web to research the following queries: {queries_combined}."
                f"\n If I need anything, I will make sure to ask you."
            )
        if not queries and len(queries) == 0:
            project_manager.add_message_from_devika(
                project_name,
                "I think I can proceed without searching the web."
            )

        ask_user_prompt = "Nothing from the user."

        if ask_user != "" and ask_user is not None:
            project_manager.add_message_from_devika(project_name, ask_user)
            agent_state.set_agent_active(project_name, False)
            got_user_query = False

            while not got_user_query:
                logger.info("Waiting for user query...")

                latest_message_from_user = project_manager.get_latest_message_from_user(project_name)
                validate_last_message_is_from_user = project_manager.validate_last_message_is_from_user(
                    project_name)

                if latest_message_from_user and validate_last_message_is_from_user:
                    ask_user_prompt = latest_message_from_user["message"]
                    got_user_query = True
                    project_manager.add_message_from_devika(project_name, "Thanks! 🙌")
                time.sleep(5)

        agent_state.set_agent_active(project_name, True)

        if queries and len(queries) > 0:
            search_results = self.search_queries(queries, project_name, engine, formatter)

        else:
            search_results = {}

        return search_results, ask_user_prompt
    
    def search_queries(self, queries: list, project_name: str, engine: str, formatter: Formatter) -> dict:
        results = {}

        # knowledge_base = KnowledgeBase()

        if engine == "bing":
            web_search = BingSearch()
        elif engine == "google":
            web_search = GoogleSearch()
        else:
            web_search = DuckDuckGoSearch()

        logger.info(f"\nSearch Engine :: {engine}")

        for query in queries:
            query = query.strip().lower()

            # knowledge = knowledge_base.get_knowledge(tag=query)
            # if knowledge:
            #     results[query] = knowledge
            #     continue

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            web_search.search(query)

            link = web_search.get_first_link()
            print("\nLink :: ", link, '\n')
            if not link:
                continue
            browser, raw, data = loop.run_until_complete(self.open_page(project_name, link))
            emit_agent("screenshot", {"data": raw, "project_name": project_name}, False)
            results[query] = formatter.execute(data, project_name)

            logger.info(f"got the search results for : {query}")
            # knowledge_base.add_knowledge(tag=query, contents=results[query])
        return results
    
    async def open_page(self, project_name, url):
        browser = await Browser().start()

        await browser.go_to(url)
        _, raw = await browser.screenshot(project_name)
        data = await browser.extract_text()
        await browser.close()

        return browser, raw, data
