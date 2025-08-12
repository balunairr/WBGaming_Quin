import json
import pandas as pd
import sqlite3



def str_to_dict(s):
    """
    Converts a JSON-formatted string into a Python dictionary.

    This function takes a string in JSON format and deserializes it into a Python 
    dictionary using the `json.loads` method.

    Args:
        s (str): The JSON-formatted string to convert.

    Returns:
        dict: A dictionary representation of the JSON string.

    Raises:
        json.JSONDecodeError: If the input string is not valid JSON.

    Notes:
        - Ensure that the input string is properly formatted as JSON; otherwise, 
          a `json.JSONDecodeError` will be raised.

    Example:
        json_string = '{"name": "John", "age": 30}'
        result = str_to_dict(json_string)
        print(result)  # Output: {'name': 'John', 'age': 30}
    """
    return json.loads(s)


def get_log(dbname="logs.db", table="chat_completions"):
    """
    Retrieves all records from a specified SQLite database table and returns them as a list of dictionaries.

    This function connects to the given SQLite database, executes a query to fetch all rows from the specified 
    table, and formats the results into a list of dictionaries where the keys are the column names.

    Args:
        dbname (str, optional): The name of the SQLite database file. Defaults to `"logs.db"`.
        table (str, optional): The name of the table to retrieve records from. Defaults to `"chat_completions"`.

    Returns:
        list of dict: A list of dictionaries, where each dictionary represents a row in the table. 
        The keys in the dictionary are the column names, and the values are the corresponding row values.

    Raises:
        sqlite3.Error: If there is an issue connecting to the database or executing the query.

    Notes:
        - Ensure that the SQLite database file (`dbname`) exists and contains the specified table (`table`) 
          before calling this function.
        - The column names in the table are used as dictionary keys.

    Example:
        logs = get_log(dbname="application_logs.db", table="user_actions")
        for log in logs:
            print(log)
    """
    import sqlite3
    con = sqlite3.connect(dbname)
    query = f"SELECT * from {table}"
    cursor = con.execute(query)
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    data = [dict(zip(column_names, row)) for row in rows]
    con.close()
    return data


def log_processing(logging_session_id):
    """
    Processes log data for a specific logging session and extracts relevant details.

    This function filters log data for a given `logging_session_id` and transforms it 
    into a Pandas DataFrame with additional columns derived from the request and response 
    content, as well as token usage statistics.

    Args:
        logging_session_id (str): The session ID used to filter the log data.

    Returns:
        pandas.DataFrame: A DataFrame containing the following columns:
            - `prev_agent`: The name of the agent responsible for the last message in the request.
            - `completion_tokens`: The number of tokens used for the model's response.
            - `prompt_tokens`: The number of tokens used in the prompt.
            - `total_tokens`: The total number of tokens used (prompt + completion).
            - `request`: The content of the user's request.
            - `response`: The content of the model's response.

    Raises:
        KeyError: If required keys are missing in the log data.
        TypeError: If the log data is not in the expected format.

    Example:
        logging_session_id = "12345"
        processed_logs = log_processing(logging_session_id)
        print(processed_logs.head())

    Notes:
        - The function assumes that the `get_log()` function returns a list of logs, 
          where each log is a dictionary containing `session_id`, `request`, and `response`.
        - The `str_to_dict` function is expected to convert JSON-like strings into Python dictionaries.
        - Ensure that the log data contains the required structure for the function to work properly.
    """
    ## Get all the logs from the db
    log_data = get_log()
    # check log data present or not
    if log_data:
        # Convert into pandas dataframe
        log_data_df = pd.DataFrame(log_data)
        ## Filter the logs only for current session question
        log_data_df=log_data_df.loc[log_data_df['session_id']==logging_session_id]
        ## check any log recorded for the session id
        if log_data_df.shape[0]!=0:
            # log_data_df["prev_agent"] = log_data_df.apply(lambda row: str_to_dict(row["request"])['messages'][-1]['name'], axis=1)
            log_data_df["completion_tokens"] = log_data_df.apply(lambda row: str_to_dict(row["response"])["usage"]["completion_tokens"], axis=1)
            log_data_df["prompt_tokens"] = log_data_df.apply(lambda row: str_to_dict(row["response"])["usage"]["prompt_tokens"], axis=1)
            log_data_df["total_tokens"] = log_data_df.apply(lambda row: str_to_dict(row["response"])["usage"]["total_tokens"], axis=1)
            # log_data_df["request"] = log_data_df.apply(lambda row: str_to_dict(row["request"])["messages"][0]["content"], axis=1)
            # log_data_df["response"] = log_data_df.apply(lambda row: str_to_dict(row["response"])["choices"][0]["message"]["content"], axis=1)
            log_status=1
        else:
            log_data_df=None
            log_status=0
            print(f"No Logs for {logging_session_id}")
    else: 
        log_data_df=None
        log_status=0
        print("No Logs")
        
    return log_data_df,log_status

def clear_logs(logging_session_id,dbname="logs.db", table="chat_completions"):
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect(dbname)
        cursor = conn.cursor()
        
        # Delete rows from the specified table and logging_session_id
        cursor.execute(f"DELETE FROM {table} WHERE session_id = ?", (logging_session_id,))

        # Commit changes
        conn.commit()
        print(f"Cleared table: {table}")
    except sqlite3.OperationalError as e:
        print(f"Error: {e}")
        
    finally:
        # Ensure the connection is closed
        conn.close()