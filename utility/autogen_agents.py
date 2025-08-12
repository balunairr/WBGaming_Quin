from autogen import Agent, AssistantAgent
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union
from dotenv import load_dotenv
import os
import pandas as pd
import sqlite3
import autogen
import re
from utility.agent_prompts import get_data_analyst_system_message,get_insights_generator_system_message,get_planner_system_message,get_sql_critic_system_message,get_sql_query_executor_system_message
from utility.tool_call import SQLToolkit
import streamlit as st
import time
import numpy as np


load_dotenv()



class SQLExecutorAgent(AssistantAgent):
    """
    A specialized agent that integrates with a SQL database to generate and execute SQL queries 
    based on user inputs, and then returns the query results formatted to fit within the model's 
    token constraints.
    
    Attributes:
        name (str): The name of the agent.
        llm_config (dict): Configuration for the large language model (LLM).
        system_message (str): Initial system message for the agent.
        human_input_mode (str): Mode for handling human inputs.
    """

    def __init__(self, name, llm_config: dict, system_message: str, human_input_mode:str, **kwargs):
        """
        Initialize the SQLExecutorAgent with the specified parameters.

        Parameters:
            name (str): The agent's name.
            llm_config (dict): Configuration for the large language model (LLM).
            system_message (str): Initial system message for the agent.
            human_input_mode (str): Mode for handling human inputs.
            kwargs: Additional optional parameters.
        """
        super().__init__(name, llm_config=llm_config, system_message=system_message, human_input_mode=human_input_mode, **kwargs)
        self.register_reply([Agent, None], SQLExecutorAgent.generate_sql_reply)
        self.response = None

    def send(self, message: Union[Dict, str], recipient: Agent, request_reply: Optional[bool] = None, silent: Optional[bool] = False):
        """
        Override the send method to automatically silence log outputs.

        Parameters:
            message (Union[Dict, str]): The message to send.
            recipient (Agent): The agent receiving the message.
            request_reply (Optional[bool]): Whether a reply is requested.
            silent (Optional[bool]): Whether to suppress output logging.
        """
        super().send(message, recipient, request_reply, silent=True)

        
    @staticmethod
    def connect_sql(query: str):
        try:
            # file_path=st.secrets.file.file_path or os.getenv('file_path')
            # sheet_name=st.secrets.file.sheet_name or  os.getenv('sheet_name')
            # table_name=st.secrets.file.table_name or os.getenv('table_name')
            # if file_path.endswith(".xlsx"):
            #     print("SQL Executor Agent :: File Loaded ::",file_path)
            #     # Load the Excel sheet into a pandas DataFrame
            #     df = pd.read_excel(file_path, sheet_name=sheet_name)
            # else:
            #     print("SQL Executor Agent :: File Loaded ::",file_path)
            #     df = pd.read_csv(file_path)
            
            # Create an in-memory SQLite database
            conn = sqlite3.connect("database.db")

            # # Load the DataFrame into the SQLite database
            # df.to_sql(table_name, conn, index=False, if_exists="replace")

            # Execute the SQL query
            df1 = pd.read_sql_query(query, conn)
            
            return df1  # Return the DataFrame with query results
        
        except Exception as e:
            print("SQL query didn't work due to:", e)
            return None
        finally:
            # Close the database connection
            conn.close()
    
    
    def get_db_results(self, generated_sql_query: str):
        """
        Execute the generated SQL query and retrieve the result as a pandas DataFrame. 
        If the result is too large, truncate it to fit within the token limit.
        """
        # Execute the query to get a DataFrame
        df = self.connect_sql(generated_sql_query)
        
        # Check if DataFrame was obtained successfully
        if df is not None and not df.empty:
            print("get_db_results: Successfully obtained DataFrame with shape:", df.shape)
        else:
            print("get_db_results: Failed to obtain DataFrame or it's empty.")


        # Check if data is within limit
        if len(df)>1 and len(df) <= 20 and df is not None and not df.empty:
            # Identify column types
            print("get_db_results: Data is within limit.")
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            datetime_cols = df.select_dtypes(include=[np.datetime64]).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            order_col=numeric_cols + datetime_cols + categorical_cols
            df = df.sort_values(by=order_col, ignore_index=True,ascending=False)
            return df, 'within-limit'

        elif len(df)==1:
            print("get_db_results: Data one limit; truncating.")
            return df, 'one-limit'

        elif df is None or df.empty:
            print("get_db_results: Data zero limit; truncating.")
            return df, 'zero-limit'

        else:
            # Identify column types
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            datetime_cols = df.select_dtypes(include=[np.datetime64]).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            order_col=numeric_cols + datetime_cols + categorical_cols
            df = df.sort_values(by=order_col, ignore_index=True,ascending=False)
            print("get_db_results: Data exceeds limit; truncating.")
            return df, 'exceeding-limit'


    @staticmethod
    def extract_sql(text):
        """
        Extract the SQL query from a block of text. The SQL query is assumed to be 
        between 'generated_sql_query:' and 'Score:' in the text.

        Parameters:
            text (str): The input text containing the SQL query.

        Returns:
            str: The extracted SQL query, or None if the pattern is not found.
        """
        # pattern = r'generated_sql_query:(.*?)Score:'  ## crtics
        pattern= r'generated_sql_query:(.*?)checklist:' ## data analyst
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None

    @staticmethod
    def extract_user_question(text):
        """
        Extract the user question from a block of text. The user question is assumed to 
        be between 'user_question:' and 'generated_sql_query:'.

        Parameters:
            text (str): The input text containing the user question.

        Returns:
            str: The extracted user question, or None if the pattern is not found.
        """
        pattern = r'user_question:(.*?)generated_sql_query:'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None


    def generate_sql_reply(self, messages: Optional[List[Dict]], sender: "Agent", config):
        """
        Generate a reply using the SQL database by executing the extracted SQL query 
        and returning the result as a DataFrame directly.
        """
        if messages is None:
            messages = self._oai_messages[sender]
        
        previous_msg = messages[-2]["content"]
        print(previous_msg)
        # Extract SQL query and user question
        sql_query_ = self.extract_sql(previous_msg).strip('`').strip('```').lstrip('sql').strip()
        user_question = self.extract_user_question(previous_msg).strip()

        print("----------------------------------------------\n Extracted SQL query:", sql_query_)
        print("Extracted user question:", user_question)

        # Execute SQL query to get DataFrame and data size flag
        db_results, data_size_flag = self.get_db_results(sql_query_)
        db_results_json = db_results.to_json(orient="records")
        print("generate_sql_reply: Data size flag from get_db_results:", data_size_flag)
        print("generate_sql_reply: Resulting DataFrame shape:", db_results.shape)
        print("GENERATE SQL REPLY RUNNING")

        # Prepare response based on data size flag
        if data_size_flag == 'within-limit':
            db_results_content = f"""
				user_question: {user_question}
				generated_sql_query: {sql_query_}
				data_size_flag: {data_size_flag}
				db_results: {db_results.to_csv()}
				TERMINATE-AGENT
				"""
            response = {
				"user_question":user_question,
				"content": db_results_content,
				"generated_sql_query": sql_query_,
				"data_size_flag": data_size_flag,
				"df": db_results_json ,
				"role": "user",
				"name": "sql_query_executor"
			}
            print("generate_sql_reply: Response content:", db_results_content)
        
        elif data_size_flag == 'exceeding-limit':
            db_results_content = f"""
				user_question: {user_question}
				generated_sql_query: {sql_query_}
				db_result: Exceeding limit, please download
				data_size_flag: {data_size_flag}
				TERMINATE-AGENT
				"""
            response = {
				"user_question":user_question,
				"content": db_results_content,
				"generated_sql_query": sql_query_,
				"data_size_flag": data_size_flag,
				"df": db_results_json,
				"role": "user",
				"name": "sql_query_executor"
			}
            print("generate_sql_reply: Prepared response exceeding limit.")
        elif data_size_flag == 'one-limit':
            db_results_content = f"""
				user_question: {user_question}
				generated_sql_query: {sql_query_}
				data_size_flag: {data_size_flag}
				TERMINATE-AGENT
				"""
            response = {
				"user_question":user_question,
				"content": db_results_content,
				"generated_sql_query": sql_query_,
				"data_size_flag": data_size_flag,
				"df": db_results_json ,
				"role": "user",
				"name": "sql_query_executor"}
            print("generate_sql_reply: one-limit")
        elif data_size_flag == 'zero-limit':
            db_results_content = f"""
				user_question: {user_question}
				generated_sql_query: {sql_query_}
				data_size_flag: {data_size_flag}
				TERMINATE-AGENT
				"""
            response = {
				"user_question":user_question,
				"content": db_results_content,
				"generated_sql_query": sql_query_,
				"data_size_flag": data_size_flag,
				"df": db_results_json ,
				"role": "user",
				"name": "sql_query_executor"
			}
            print("generate_sql_reply: Sorry, I wasn't able to generate the correct query. Would you like to rephrase the question?", db_results_content)
        self.response =response
        return True, response

def check_name_occurrences(data, name_value, no_of_iters):
    '''Checks how many times critic_agent or insights_agent have responded. This helps to end the loop'''
    count = sum(1 for entry in data if entry.get('name') == name_value)
    return count >= no_of_iters
    
def check_name_occurrences_tool(data, name_value,function_tool, no_of_iters):
    '''Checks how many times critic_agent or insights_agent have responded. This helps to end the loop'''
    data=[entry for entry in data if entry.get("role")=="function"]
    count = sum(1 for entry in data if entry.get("name")==function_tool)
    print(f"Agent Name ::{name_value} , Tool Name ::{function_tool} , Count :: {count}")
    return count >= no_of_iters



def initiate_chat(user_question,data_dictionary_prompt): # async
    print("Step 2) -------Tool initialization-------------")
    tool_start_time=time.time()
    tool_obj=SQLToolkit()
    tools,function_map=tool_obj.initialize_tools()
    tool_end_time=time.time()
    tool_time=tool_end_time-tool_start_time
    print("---------Tools initialized---------")

    print("-------Set LLM Configuration for Azure OpenAI-------------")
    agent_i_start_time=time.time()
    llm_config_azure = [
        {
            "model": st.secrets.azure.model or  os.getenv("model"),
            "api_key": st.secrets.azure.api_key or  os.getenv("api_key"),
            "base_url": st.secrets.azure.base_url or  os.getenv("base_url"),
            "api_type": st.secrets.azure.api_type or  os.getenv("api_type"),
            "api_version": st.secrets.azure.api_version or  os.getenv("api_version")
        }
    ]
    # General LLM config for the agent
    llm_config = {"config_list": llm_config_azure}

    # LLM config for Data Analyst Agent, which contains tools
    llm_config_lst = {
        "functions": tools,
        "config_list": llm_config["config_list"],
        "temperature":0.05,
        "timeout": 120,
        "stream": True
    }

    ##----------------------------------------------------------------------------------
    # LLM config for other Agent, which not contains any tools
    llm_config_common = {
        # "functions": tools,
        "config_list": llm_config["config_list"],
        "temperature":0.05,
        "timeout": 120,
        "stream": True
    }
    

    print("-------USER PROXY AGENT-------------")
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="A human admin. Once the task is completed, answer 'TERMINATE-AGENT'",
        human_input_mode="NEVER",
        code_execution_config=False
    )


    print("-------PLANNER AGENT-------------")
    planner_system_message=get_planner_system_message(data_dictionary_prompt)
    planner = autogen.AssistantAgent(
        name="planner",
        system_message=planner_system_message ,
        human_input_mode="NEVER",
        llm_config=llm_config_common
    )

    print("-------Data Analyst Agent-------------")
    data_analyst_system_message=get_data_analyst_system_message(data_dictionary_prompt)
    data_analyst = autogen.AssistantAgent(
        name="data_analyst",
        system_message=data_analyst_system_message,
        human_input_mode="NEVER",
        llm_config=llm_config_lst) # Assuming this contains the necessary tools for data analysis

    data_analyst.register_function(function_map=function_map)

    print("-------SQL CRITIC Agent-------------")
    sql_critic_system_message=get_sql_critic_system_message(data_dictionary_prompt)
    sql_critic = autogen.AssistantAgent(
        name="sql_critic",
        system_message=sql_critic_system_message ,
        human_input_mode="NEVER",
        llm_config=llm_config_common
    )

    print("-------SQL Executor Agent-------------")
    sql_query_executor_system_message=get_sql_query_executor_system_message()
    sql_query_executor = SQLExecutorAgent(
        name="sql_query_executor",
        system_message=sql_query_executor_system_message,
        human_input_mode="NEVER",
        llm_config=llm_config_common
    )

    print("-------INSHIGHTS GENERATOR Agent-------------")
    insights_generator_system_message=get_insights_generator_system_message()
    insights_generator = autogen.AssistantAgent(
        name="insights_generator",
        system_message=insights_generator_system_message,
        human_input_mode="NEVER",
        llm_config=llm_config_common
        )

    print("-------Terminator Agent-------------")
    terminator_system_message = f"""

You need to answer with 'max-3-tries'. Do NOT add any introductory phrase or do NOT explain anything else.

"""
    terminator = autogen.AssistantAgent(
        name="terminator",
        system_message=terminator_system_message,
        human_input_mode="NEVER",
        llm_config=llm_config_common
    )

    def state_transition(last_speaker, groupchat):
        '''Function to define a structured navigation of agents in the flow.'''
        messages = groupchat.messages
        last_message = messages[-1]
        
        if len(messages)==1:
            text=f'1st Speaker Name: {last_speaker.name}. Start the agent now.'
        else:
            text=f'Current Speaker Name: {last_speaker.name}. End the Excution.'

    
        if last_speaker is user_proxy:
            # init -> retrieve
            if len(messages) == 1:
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name: Planner Start'
            
                return planner # planner data_analyst
            
            elif messages[-1]['role'] == 'tool':
            
                return sql_query_executor
            
            else:
                return data_analyst

        elif last_speaker is planner:
            if 'terminate-agent' in messages[-1]["content"].lower():
                return data_analyst
            elif "terminate-flow" in messages[-1]["content"].lower():
                return terminator
            else:
                return planner

        elif last_speaker is data_analyst:
            if 'terminate-agent' in messages[-1]["content"].lower():
                # retrieve --(execution failed)--> retrieve
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name: sql_critic Start'
                
                return sql_critic
            elif check_name_occurrences_tool(messages, 'data_analyst',"sql_db_query_run", 5):
                return terminator
            else:
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name: Data Analyst Start'
            
                return data_analyst  # data_analyst

        elif last_speaker is sql_critic:
            if 'all-good' in messages[-1]["content"].lower():
                # retrieve --(execution failed)--> retrieve
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:sql_query_executor Start'
            
                return sql_query_executor
            elif check_name_occurrences(messages, 'sql_critic', 3):
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:terminator Start'
            
                return terminator
            else:
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:Data Analyst Start'
            
                return data_analyst

        elif last_speaker is sql_query_executor:
            # Determine flow based on data size flag in the last message
            if "exceeding-limit" in last_message.get('content'):
                data_size_flag = "exceeding-limit"
            if "within-limit" in last_message.get('content'):
                data_size_flag = "within-limit"
            if "zero-limit" in last_message.get('content'):
                data_size_flag = "zero-limit"
            if "one-limit" in last_message.get('content'):
                data_size_flag = "one-limit"

            print("THE RESPONSE IS ",sql_query_executor.response)

            if data_size_flag == 'within-limit':
                # Data size within limit, proceed to insights generation
                text=f'Last Speaker Name: {last_speaker.name} ::  Current Speaker Name: insights_generator Start -within-limit'
            
                return insights_generator
            
            elif data_size_flag == 'exceeding-limit':
                # Data size exceeds limit, skip insights generation and go to terminator
                text=f'Last Speaker Name: {last_speaker.name} ::  Current Speaker Name:terminator Start - exceeding-limit'
                
                return terminator

            elif data_size_flag == "zero-limit":
                return terminator
            
            elif data_size_flag == "one-limit":
                return terminator
                
            else:
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:user_proxy Start'
            
                return user_proxy

        elif last_speaker is insights_generator:
            if 'all-good-completed' in last_message["content"].lower():
                # End process after generating insights if completed
                return None
            else:
                text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:terminator Start'
                # Move to terminator if not completed
                return terminator

        elif last_speaker is terminator:
            text=f'Last Speaker Name: {last_speaker.name} :: Current Speaker Name:terminator Start'
        
            return None

    #group chat is required to let all the agents interact with each other 
    groupchat = autogen.GroupChat(
        agents=[user_proxy,planner,data_analyst,sql_critic,sql_query_executor,insights_generator,terminator],   
        messages=[],                        
        max_round=50,                         
        speaker_selection_method=state_transition
    )
    # Initialize the GroupChatManager with the GroupChat
    manager_system_message = """You are the manager. You are responsible for the task to be executed correctly by every agent. You need to provide a final summary / answer to the user query as response by looking into the answers of all agents.
    Project flow:
    1. data_analyst will understand the user query, look into the database, frame SQL query and return it
    2. user_proxy will check if the process is done properly"""

    manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=manager_system_message                                 
    )
    agent_i_end_time=time.time()
    agent_i_time=agent_i_end_time-agent_i_start_time
    logging_session_id = autogen.runtime_logging.start(config={"dbname": "logs.db"})
    print("Logging session ID: " + str(logging_session_id))
    try:
        agent_call_start_time=time.time()
        result=user_proxy.initiate_chat(manager, 
                            message=user_question)  
        agent_call_end_time=time.time()
        agent_call=agent_call_end_time-agent_call_start_time
        inf_time={"tool_time":tool_time,
                "agent_i_time":agent_i_time,
                "agent_call":agent_call}
        response={"chat_history":result.chat_history,
            "sql_execution_response":sql_query_executor.response,
            "message":"ok"} 
        return response,logging_session_id,inf_time
    except Exception as e:
        print("Exception At Agent Initiate ::",e)
        response={"chat_history":result.chat_history,
            "sql_execution_response":sql_query_executor.response,
            "message":"ok"}
        inf_time={}
        return response,logging_session_id,inf_time
