# from langchain.sql_database import SQLDatabase
from langchain_community.utilities.sql_database import SQLDatabase
from sqlalchemy import create_engine
from langchain_openai import AzureChatOpenAI
from openai import AzureOpenAI
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
import pandas as pd
import os
from dotenv import load_dotenv
import streamlit as st
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import sqlite3
import re 

load_dotenv()


class DataInput(BaseModel):
    query:str = Field(description="the user input query")
    table_name: str = Field(description="The name of table")
    column_name: str = Field(description="The name of column to retrieve distinct values.")


@tool()
def fetch_distinct_values(look_up_value:str ,table_name: str, column_name: str):
    """Always Use this `fetch_distinct_values` tool to retrieve distinct values for specific columns in a SQLlite database table. The result can be used to find variations of a category which are not standardized. The "look_up_value" refers to the value we search for in the list of unique values."""
    # Step 1: Preprocess the text to extract keywords
    def preprocess_text(text):
        # Lowercase, remove special characters, numbers, and tokenize
        text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove punctuation
        return text.lower().split()  # Split into words
    query_keywords = preprocess_text(look_up_value)

    # Step 2: Define a function to calculate match percentage
    def calculate_match_percentage(row, keywords):
        if row!=None:
            target_keywords = preprocess_text(row.lower())  # Preprocess target text
            common_keywords = set(keywords) & set(target_keywords)  # Find common keywords
            match_percentage = len(common_keywords) / len(keywords) * 100  # Calculate match percentage
            return match_percentage
        else:
            return 0
        
    results={}
    try:
        # Instantiate the tool
        conn = sqlite3.connect("database.db")
        
        query = f"SELECT DISTINCT {column_name} FROM {table_name}"
        df1 = pd.read_sql_query(query, conn)

        # Step 3: Apply the match percentage function to the target column
        df1['match_percentage'] = df1[column_name].apply(lambda x: calculate_match_percentage(x, query_keywords))
        df1=df1.sort_values("match_percentage",ascending=False).head(15)
        results[column_name] = df1[column_name].to_list()
        return results

    except Exception as e:
        return {"error": str(e)}




class SQLToolkit():

    def __init__(self) -> None:
        # self.file_path= st.secrets.file.file_path or os.getenv('file_path')
        # self.sheet_name=st.secrets.file.sheet_name  or os.getenv('sheet_name')
        self.table_name=st.secrets.file.table_name or os.getenv('table_name')
        # print("File Path ::",self.file_path)

    def generate_llm_config(self,tool):
        '''Generates a function schema for a given tool to be used in configuring an LLM.

        The function constructs a schema for the tool, defining its name, description, 
        and the parameters required for its operation. If the tool has arguments 
        (provided in the 'args_schema'), these will be included in the schema.
        
        Parameters:
        tool (object): An object representing a tool, which must have the following attributes:
            - name (str): The name of the tool.
            - description (str): A description of what the tool does.
            - args (dict, optional): The arguments required by the tool (if any).

        Returns:
            dict: A schema that defines the function's structure, including:
                - name (str): The tool name, formatted as lowercase and replacing spaces with underscores.
                - description (str): A description of the tool's purpose.
                - parameters (dict): A nested dictionary with the type, properties, and required parameters.

        '''
        function_schema = {
            "name": tool.name.lower().replace(" ", "_"),
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        }
        if tool.args is not None:
            function_schema["parameters"]["properties"] = tool.args
        return function_schema

    def initialize_tools(self):
        # Load the Excel sheet into a pandas DataFrame
        # if self.file_path.endswith(".xlsx"):
        #     print("Toolkit :: File Loaded ::",self.file_path)
        #     df = pd.read_excel(self.file_path, sheet_name=self.sheet_name)
        # else:
        #     print("Toolkit :: File Loaded ::",self.file_path)
        #     df = pd.read_csv(self.file_path)
            
        # Create an SQLAlchemy engine for SQLite (in-memory)
        # engine = create_engine('sqlite:///:memory:')
        engine = create_engine(f"sqlite:///database.db")
        # Load the DataFrame into the SQLite database
        # df.to_sql(self.table_name, engine, index=False, if_exists="replace")
        db = SQLDatabase(engine=engine, lazy_table_reflection=True)
        openai = AzureChatOpenAI(
                        azure_endpoint= st.secrets.azure.base_url or os.getenv('base_url'),
                        deployment_name=st.secrets.azure.model or os.getenv('model'),
                        openai_api_key=st.secrets.azure.api_key or os.getenv('api_key'),
                        openai_api_version=st.secrets.azure.api_version or os.getenv('api_version'),
                        temperature=0)
        # openai = AzureOpenAI(
        #                     azure_endpoint=st.secrets.azure.base_url or os.getenv('base_url'),
        #                     azure_deployment=st.secrets.azure.model or os.getenv('model'),
        #                     api_version=st.secrets.azure.api_version or os.getenv('api_version'),
        #                     api_key=st.secrets.azure.api_key or os.getenv('api_key'),
        #                     temperature=0)
        # Initialize the SQLDatabaseToolkit for executing SQL queries with LLM assistance
        toolkit = SQLDatabaseToolkit(db=db, llm=openai)
        # Generate list of tools and function map
        tools = []
        function_map = {}
        for tool in toolkit.get_tools():
            if tool.name =="sql_db_query":
                tool.name="sql_db_query_run"
                tool_description = """Input to this tool is a detailed and correct SQL query for the user question, output is a result from the database. If the query is not correct, an error message will be returned. If an error is returned, rewrite the query, check the query, and try again."""
                tool_schema = self.generate_llm_config(tool)
                tool_schema['description']=tool_description
                tools.append(tool_schema)
                tool.description = tool_description
                function_map[tool.name] = tool._run
                
            # elif tool.name =="sql_db_query_checker":
            #     tool_desc="""Use this tool to double check if your query is correct before executing it. Always use this tool before executing a query with sql_db_query_run tool!"""
            #     tool_schema = self.generate_llm_config(tool)
            #     tool_schema['description']=tool_desc
            #     tools.append(tool_schema)
            #     tool.description = tool_desc
            #     function_map[tool.name] = tool._run

        tool_schema = self.generate_llm_config(fetch_distinct_values)
        tools.append(tool_schema)
        function_map[fetch_distinct_values.name] = fetch_distinct_values._run

        return tools,function_map
            
