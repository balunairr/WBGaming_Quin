# GA-Quin-Assistant


# How to run the Streamlit application

1. Install of required dependaices 

```bash
pip install -r requirements.txt
```


2. Run the Application using following Command
```bash
streamlit run app.py
```


### Agentic Workflow- 
1.	Planner Agent – Break down the user question into multiple chunks and suggest valid points on how to perform the operations, clauses, and add constraints
2.	Data Analyst Agent- Understand the intent of the user query thoroughly before framing the SQL query, ensuring it translates the query correctly with all necessary details.
3.	Critics Agent - Evaluate an SQL query generated based on a intent of the user question and has to provide a score either 0 or 1. If the SQL query execution results in an error, give a numeric score of 0 and provide a critic message
4.	SQL Executor Agent- Executing SQL queries and fetching results from database.
5.	Insight Generator Agent- Analyze the dataframe provided by SQL executor agent and provide textual insights and plots based on the user question.
6.	Terminate Agent- Stop the execution.




