import os
from dotenv import load_dotenv
from openai import AzureOpenAI
import openai
import streamlit as st

AZURE_OPEN_AI_DEPLOYMENT_NAME = st.secrets.azure.model or os.getenv('model')
AZURE_OPEN_AI_KEY = st.secrets.azure.api_key or os.getenv('api_key')
AZURE_OPEN_AI_URL = st.secrets.azure.base_url or os.getenv('base_url')
AZURE_OPEN_AI_VERSION = st.secrets.azure.api_version or os.getenv('api_version')

## Azure Open AI Client
client = AzureOpenAI(
    azure_endpoint=AZURE_OPEN_AI_URL,
    api_version=AZURE_OPEN_AI_VERSION,
    api_key=AZURE_OPEN_AI_KEY)


def one_limit_call(prompt_):
    try:
        # Create completion request
        completion = client.chat.completions.create(
            model=AZURE_OPEN_AI_DEPLOYMENT_NAME,
            temperature=0,
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant expert in analyzing data.'},
                {"role": "user", "content": prompt_}
            ]
        )
        usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens
            }
        
        return completion.choices[0].message.content, usage

    except Exception as e:
        print("Exception in one_limit_call Azure Call:", e)


def refine_question(history,user_question): # async
    history_prompt=""
    for dict1 in history:
        prompt_1=dict1['role']+":" +dict1['content']+"\n"
        history_prompt+=prompt_1
    
    refine_question_prompt=f"""You are assistent and given the user's history. If assistent replied the user's query is unrelated, must write the same user provided input question. If assistent ask additional details or clarifications are required for the question to be effectively answered, incorporate user input into the refinements into the final version of the query.
    user_history:{history_prompt}
    user input:{user_question}
    question: """
    client = AzureOpenAI(
    azure_endpoint=AZURE_OPEN_AI_URL,
    api_version=AZURE_OPEN_AI_VERSION,
    api_key=AZURE_OPEN_AI_KEY)
    completion = client.chat.completions.create(
            model=AZURE_OPEN_AI_DEPLOYMENT_NAME,
            temperature=0,
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant analysing the customer history.'},
                {"role": "user", "content": refine_question_prompt}
            ]
        )
    usage = {
            "prompt_tokens": completion.usage.prompt_tokens,
            "completion_tokens": completion.usage.completion_tokens
            }

    return completion.choices[0].message.content, usage

def sql_explanation(sql_query):
    """
    Generates a plain-language explanation of an SQL query using Azure OpenAI's Chat API.

    This function connects to the Azure OpenAI API to interpret and explain the provided SQL query 
    in a way that is understandable to business analysts. The explanation is structured as a list 
    of bullet points for clarity and avoids direct reference to the query text, ensuring a concise 
    and logical summary of the query's purpose and functionality.

    Args:
        sql_query (str): The SQL query to be explained. This should be a valid SQL query.

    Returns:
        tuple:
            - explanation (str): A plain-language explanation of the SQL query in bullet point format.
            - usage (dict): A dictionary containing token usage information with the following keys:
                - `prompt_tokens`: The number of tokens used in the prompt.
                - `completion_tokens`: The number of tokens used in the response.

    Raises:
        Exception: If an error occurs while interacting with the Azure OpenAI API.

    Example:
        sql_query = "SELECT customer_name, SUM(order_amount) FROM orders WHERE order_date >= '2023-01-01' GROUP BY customer_name;"
        explanation, usage = sql_explanation(sql_query)
        print("Explanation:\n", explanation)
        print("Token Usage:", usage)

    Notes:
        - The function assumes that the Azure OpenAI environment is configured with the required API key and endpoint.
        - The model used for generating explanations is specified by the `AZURE_OPEN_AI_DEPLOYMENT_NAME` constant.
        - The API call expects the OpenAI client (`client`) to be initialized beforehand.
        - The function is designed specifically for SQL queries and provides tailored explanations for business analysts.

    Example Output for Query:
        Input SQL Query: 
        SELECT customer_name, SUM(order_amount) FROM orders WHERE order_date >= '2023-01-01' GROUP BY customer_name;

        Example Output Explanation:
        - Identifies the total amount each customer has spent since January 1, 2023.
        - Retrieves data from the "orders" table, filters for transactions after the specified date, 
          and groups the results by customer to calculate their total spending.
        - Provides insights into customer purchasing trends for better sales analysis.
    """
    openai.api_type = "azure"
    try:
        
        response = client.chat.completions.create(
            model=AZURE_OPEN_AI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a useful assistant who explains SQL queries. Your work for Mercedes Benz."},
                {"role": "user", "content": f"""
You are an expert in SQL and specialize in explaining queries to business analysts. 
When given an SQL query, provide a simple, connected explanation that tells the full story of what the query does and why it is structured that way.
Avoid displaying or referencing the query itself. 
Focus on delivering a high-quality, concise summary in plain, easy-to-understand language, ensuring continuity in the explanation so that it flows logically from start to finish.
Make sure to include the table names in the explanation for better referencing but avoid using the query as it is in the explanation.
Keep in mind to only display the table name not in the form of catalog.schema.table_name.
You can find the query in {sql_query}
Example Input:
SELECT customer_name, SUM(order_amount) FROM orders WHERE order_date >= '2023-01-01' GROUP BY customer_name;

Example Output:
This query identifies how much each customer has spent since January 1, 2023. 
It pulls data from the transaction records, filters for purchases made on or after the specified date, and then organizes the data by customer to calculate their total spending. 
The result is a clear summary of recent customer activity, helping to analyze sales trends.

Do not print the provided query again in the output 
Print the output in bullet points 
    """}],
            max_tokens=1000,
            temperature=0)
        output = response.dict()
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens
            }
        return output['choices'][0]['message']['content'],usage

    except Exception as api_exception:
        print("Error calling Azure OpenAI API:", api_exception)
        return None