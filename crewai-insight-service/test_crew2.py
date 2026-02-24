from crewai import Agent, Task
import os
os.environ["OPENAI_API_KEY"] = "NA"
task1 = Task(description='1', expected_output='1', agent=Agent(role='1',goal='1',backstory='1',allow_delegation=False), output_file='/app/data/test.json')
task2 = Task(description='2', expected_output='2', agent=Agent(role='2',goal='2',backstory='2',allow_delegation=False), output_file='./data/test.json')
task3 = Task(description='3', expected_output='3', agent=Agent(role='3',goal='3',backstory='3',allow_delegation=False), output_file='data/test.json')

print("Path 1:", task1.output_file)
print("Path 2:", task2.output_file)
print("Path 3:", task3.output_file)
