# from utility.temp_history import SessionHistoryManager
from utility.autogen_agents import initiate_chat
import streamlit as st
from utility.api_calls import refine_question
from utility.chat_helper import get_agent_chat_summary,DataDictionaryPrompt
import time


if "data_dictionary_prompt" not in st.session_state:
    st.session_state.data_dictionary_prompt=None


def chat(user_question): # async
    usage={'prompt_tokens': 0, 'completion_tokens': 0}
    dict_prompt_start_time=time.time()
    if st.session_state.data_dictionary_prompt==None:
        print("Step-1) -------------Data Dictionary prompt---------------------")
        dict_obj=DataDictionaryPrompt()
        st.session_state.data_dictionary_prompt,st.session_state.date_range=dict_obj.get_prompt()
        print("Step-1) -------------Data Dictionary Prompt Ready---------------------")
    else:
        print("Step-1) -------------Data Dictionary Prompt Ready---------------------")
    dict_prompt_end_time=time.time()
    dict_prompt_time=dict_prompt_end_time-dict_prompt_start_time

    # Intiate Chat
    if len(st.session_state.history_manager)==0:
        print("---------------------No Follow up---------------------------")
        result, logging_session_id,inf_time= initiate_chat(user_question,st.session_state.data_dictionary_prompt) # await
     
    else:
        print("---------------------Follow Up---------------------------")
        user_question,refine_usage= refine_question(st.session_state.history_manager,user_question) # await
        print("Refine Question:", user_question)
        result, logging_session_id,inf_time= initiate_chat(user_question,st.session_state.data_dictionary_prompt) # await
        usage['prompt_tokens'] += refine_usage["prompt_tokens"]
        usage['completion_tokens'] += refine_usage["completion_tokens"]
        print("total usage is:", usage)
  
    # Step 5: Generating Response Summary
    chat_summary_start_time=time.time()
    final_response = get_agent_chat_summary(result, usage, logging_session_id, user_question) # await
    print(final_response)
    chat_summary_end_time=time.time()
    chat_summary_time=chat_summary_end_time-chat_summary_start_time
    inf_time["dict_prompt_time"]=dict_prompt_time
    inf_time["chat_summary_time"]=chat_summary_time
    print("-------------------Time-----------------------------")
    print(inf_time)
    final_response['Total_time']=sum(list(inf_time.values()))
    return final_response
