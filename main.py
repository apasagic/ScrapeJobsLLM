from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time
import openai
import yaml
import json
import tiktoken
import scraper
import chroma_db
from utilities import scrape_job_remoteok, generate_html_report, send_email, remove_duplicates,extract_chroma_entry

#from llama_cpp import Llama
from email.message import EmailMessage

def process_text(user_input):

    
    # Load configuration
    with open("config.yaml") as f:
        config = yaml.safe_load(f)
    
    # Your CV to match job fitness
    with open("cv.txt", "r", encoding="utf-8") as f:
        my_cv = f.read()
    
    user_email = "dr.amir.pasagic@gmail.com"
    
    job_scraper  = scraper.JobScraper(config = config, my_cv=my_cv)
    
    jobs,jobs_query_text = job_scraper.scrape_job("remoteok")
    
    # Extract the job rows
    #job_html_snippet = "\n".join(str(card) for card in job_cards[:36])  # 20 jobs max
    
    prompt = f"""
    Please analyze the following list of remote machine-learning jobs and write in summary, what are most sought skills, what are the most common job titles, and what are the most common tags.
    I am a junior machine learning engineer, and I want to know what skills I should focus on to get a job in this field.
    I am also curious which particular fields in machine learning are most in demand. Here is the list of jobs:
    
    {jobs_query_text},
    
    Please take in account information about my CV, which is provided below:
    {my_cv}
    """
    
    # Call the LLM
    response = job_scraper.client.chat.completions.create(
        model="deepseek/deepseek-r1-0528-qwen3-8b",  # or another from openrouter.ai/models
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    LLM_Summary = response.choices[0].message.content
    
    vector_db = chroma_db.ChromaDB()
    vector_db.add_to_vector_db(remove_duplicates(jobs))
    
    # Output
    #print(LLM_Summary)
    html_report = generate_html_report(extract_chroma_entry(vector_db.query_similar("Jobs related to time series analysis")), LLM_Summary)
    
    with open("jobs.html", "w", encoding="utf-8") as f:
        f.write(html_report)
    
    print("✅ jobs.html created with a beautiful table!")
    
    
    #print(vector_db.query_similar("Electric vehicle battery management system"))
    #print(vector_db.query_similar("Time series forecasting"))
    
    send_email(user_email, "Your Job Report", html_report)

if __name__ == "__main__":
    # Example usage
    user_input = "What are the most common skills in machine learning jobs?"
    process_text(user_input)