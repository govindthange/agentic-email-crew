from crewai import Agent, Task, Crew, Process
import os

os.environ["OPENAI_API_KEY"] = "NA"

llm = type('obj', (object,), {'predict': lambda self, text: 'Hello, World!'})()

agent = Agent(
    role='Test Agent',
    goal='Test File Output',
    backstory='You write files.',
    llm=llm,
    verbose=True,
    allow_delegation=False
)

task = Task(
    description='Write a test string.',
    expected_output='A string.',
    agent=agent,
    output_file='/app/data/test_output.json'
)

crew = Crew(
    agents=[agent],
    tasks=[task],
    process=Process.sequential
)
crew.kickoff()
