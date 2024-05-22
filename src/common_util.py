import subprocess
import re
from src.project import ProjectManager
from src.state import AgentState
import time


def exec_command(command: str, project_path: str):
    # command_set = str(command).split(" ")
    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True, 
        cwd=project_path,
        timeout=300
    )

    if process.returncode == 0:
        command_output = process.stdout.decode('utf-8') 
    else:
        command_output = f"ERROR: Command failed with exit code {process.returncode}\n{process.stderr.decode('utf-8')}"
    
    cleaned_output = re.sub(r'\x1B\[[0-?]*[ -/]*[@-~]', '', command_output)

    return process.returncode, command_output, cleaned_output

def convert_to_single_word(text):
    # Split the text into words
    words = text.split()
    
    # Capitalize each word and join them without spaces
    single_word = ''.join(word.capitalize() for word in words)
    
    return single_word
