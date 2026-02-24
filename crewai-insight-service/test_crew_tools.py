from crewai import Agent, Task, Crew
import os
os.environ["OPENAI_API_KEY"] = "NA"
try:
    from crewai_tools import FileReadTool
    print("Found crewai_tools")
except ImportError:
    print("No crewai_tools")
from crewai.tools import BaseTool

class DummyTool(BaseTool):
    name: str = "dummy"
    description: str = "dummy"
    def _run(self, *args, **kwargs):
        pass
print("Loaded BaseTool")
