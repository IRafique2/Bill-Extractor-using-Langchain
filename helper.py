from langchain.llms import OpenAI
from pypdf import PdfReader
import pandas as pd
import re
from langchain.prompts import PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.agents.agent_types import AgentType
from langchain.chains import LLMChain
from langchain_ollama import OllamaLLM
import requests
import openai
import os
from dotenv import find_dotenv, load_dotenv
load_dotenv(find_dotenv())
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
from io import BytesIO



# Load environment variables
load_dotenv(find_dotenv())
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# Ensure uploaded_file is a file-like object
def get_pdf_text(uploaded_file):
    text = ""
    
    # Check if uploaded_file is a file-like object (not a string)
    if isinstance(uploaded_file, str):
        raise TypeError("Expected a file-like object, not a string.")
    
    # Convert to BytesIO for file-like behavior
    pdf_file = BytesIO(uploaded_file.read())  # Convert to BytesIO
    pdf_reader = PdfReader(pdf_file)
    
    for page in pdf_reader.pages:
        text += page.extract_text()
    
    return text


def extracted_data(uploaded_file):
    pdf_data = get_pdf_text(uploaded_file)
    extracted_info = extract_data_from_groq(pdf_data)
    if extracted_info:
        return extracted_info
    else:
        return {}


import json
import re

import json
import re

def extract_data_from_groq(pdf_data):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    api_url = "https://api.groq.com/openai/v1/chat/completions"

    prompt = f"""
    You are a precise invoice data extractor.
    From the following invoice text, extract the fields:
    - Invoice ID
    - DESCRIPTION
    - Issue Date
    - UNIT PRICE
    - AMOUNT
    - Bill For
    - From
    - Terms

    Return only valid JSON in this format (no explanations, no markdown):

    {{
        "Invoice ID": "...",
        "DESCRIPTION": "...",
        "Issue Date": "...",
        "UNIT PRICE": "...",
        "AMOUNT": "...",
        "Bill For": "...",
        "From": "...",
        "Terms": "..."
    }}

    Invoice text:
    {pdf_data}
    """

    payload = {
        "model": "llama-3.3-70b-versatile",  # supported Groq model
        "messages": [
            {"role": "system", "content": "You are a data extraction assistant."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }

    response = requests.post(api_url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]

            # Extract the JSON substring using regex to be safe
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                parsed = json.loads(json_text)
                return parsed
            else:
                print("No valid JSON found in model response.")
                return None

        except Exception as e:
            print("Error parsing Groq response:", e)
            print("Raw model output:\n", content)
            return None
    else:
        print("Error with GroQ API:", response.status_code, response.text)
        return None


def create_docs(user_pdf_list):
    df = pd.DataFrame({'Invoice ID': pd.Series(dtype='int'),
                       'DESCRIPTION': pd.Series(dtype='str'),
                       'Issue Date': pd.Series(dtype='str'),
                       'UNIT PRICE': pd.Series(dtype='str'),
                       'AMOUNT': pd.Series(dtype='float'),
                       'Bill For': pd.Series(dtype='str'),
                       'From': pd.Series(dtype='str'),
                       'Terms': pd.Series(dtype='str')
                      })

    for pdf_file in user_pdf_list:
        if isinstance(pdf_file, str):
            with open(pdf_file, 'rb') as f:
                extracted_info = extracted_data(f)
        else:
            extracted_info = extracted_data(pdf_file)
        
        


        if extracted_info:
            amount_str = extracted_info.get("AMOUNT", "0")
            # Remove anything that's not a digit or decimal point
            amount_str = re.sub(r"[^\d.]", "", str(amount_str))
            try:
                amount_value = float(amount_str) if amount_str else 0.0
            except ValueError:
                amount_value = 0.0

            data_dict = {
                "Invoice ID": extracted_info.get("Invoice ID"),
                "DESCRIPTION": extracted_info.get("DESCRIPTION"),
                "Issue Date": extracted_info.get("Issue Date"),
                "UNIT PRICE": extracted_info.get("UNIT PRICE"),
                "AMOUNT": amount_value,
                "Bill For": extracted_info.get("Bill For"),
                "From": extracted_info.get("From"),
                "Terms": extracted_info.get("Terms")
            }

            # Append data to the dataframe
            df = pd.concat([df, pd.DataFrame([data_dict])], ignore_index=True)

    return df

