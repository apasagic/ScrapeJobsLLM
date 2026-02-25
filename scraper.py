from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from llama_cpp import Llama
from bs4 import BeautifulSoup
import re
import time
import tiktoken
import openai
import json
from utilities import scrape_job_remoteok, generate_html_report

class JobScraper:
    def __init__(self, config, my_cv, batch_size=10):
        
        self.config = config
        self.driver = self.get_driver()
        self.client = openai.OpenAI(
                    api_key=config['api']['openrouter_key'],
                    base_url=config['api']['openrouter_url'],
                   )
        
        self.download_counter = 0
        self.scraping_done = False
        self.response_text = ""
        self.jobs = []
        self.jobs_enchanced = []
        self.my_cv = my_cv
        self.batch_size = batch_size

    def get_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.binary_location = self.config['paths']['chrome']
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        service = Service(executable_path=self.config['paths']['chromedriver'])
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.get('http://google.com/')

        return self.driver

    def get_openai_client(self):
        openai.api_key = config['api']['openrouter_key']
        return openai
    
    def scrape_job(self, website):

        if website == "remoteok":
           jobs =  scrape_job_remoteok(self.driver, self.client)
           return self.compress_description(jobs, self.my_cv, self.client)

    def compress_description(self,jobs,my_cv,client):
      
      jobs_batch = []
      
      for job in jobs:

        jobs_batch.append(job)

        if( len(jobs_batch) >= self.batch_size):  # Process in batches of 10
            print(f"Processing batch of {self.batch_size} jobs...")
        else:
            continue
        
        # Create prompt
       # Create prompt
        system_prompt = """
         You are a helpful assistant for analyzing job offers for machine learning engineers. 
         For each job in the provided list:
         - Condense the description to 2-3 sentences.
         - Extract the following values and update the corresponding fields from the description and replace N/A values: 
           - seniority field: required seniority level (e.g., "Junior", "Mid-level", "Senior") from the description
           - experience field: required minimum years of working experience required (e.g., "2-3 years", "5+ years") from the description
           - skills field: comma-separated list of required skills (e.g., "Python, TensorFlow, NLP") from the description
           - salary field: usually the range of salary in USD, e.g. $60k - $80k, or 100k$ - 120k$, or 150k+ $        
         - Do this for each job individually and in any case return some value for the above mentioned fields, especially the experience and seniority, if nothing write "not specified" and replace N/A
         - Assign a 'job_fitness' score (1-10) based on how well it matches the following CV.
         - In the field "Comment" provide a short comment on why is a job a good fit for the CV. (rationale for the job_fitness score)
         - Normalize keywords: Use standard labels like 'NLP', 'RL', 'Computer Vision', etc. to ensure consistency across job descriptions and allow filtering and analysis
          
          Input is a list of JSON objects of the following structure:

                {{
               "id": "job_id",
               "title": title,
               "link": link,
               "description": description,
               "experience": "N/A",  # Placeholder for experience
               "seniority": "N/A",  # Placeholder for experience
               "skills": "N/A",  # Placeholder for skills
               "tags": ', '.join(tags),
               "salary": salary,
               "location": location,
               "source": "RemoteOK",
               "job_fitness": "N/A",  # Placeholder for job fitness
                "comment": "N/A"  # Placeholder for comment
                }}

         Return a valid JSON list of updated jobs with a same structure and length as an input, if a value is missing just write N/A.
         Do not drop any jobs, even if they are not relevant to the CV.
        """

        user_prompt = f"""CV:\n{my_cv}\n\nJobs:\n{json.dumps(jobs_batch, indent=2)}"""

        start_time = time.time()

        # Send to LLM
        response = client.chat.completions.create(
        model="deepseek/deepseek-r1-0528-qwen3-8b",
        messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
        ],
        temperature=0.3
        )

        # Extract result
        response_text_batch = response.choices[0].message.content

        # Remove Markdown formatting
        if response_text_batch.startswith("```json"):
           response_text_batch = response_text_batch.strip("```json").strip("```").strip()

        # Parse JSON from response
        try:
           jobs_enhanced_batch = json.loads(response_text_batch)
        except json.JSONDecodeError:
           print("❌ Failed to parse JSON from response.")
           jobs_enhanced_batch = []

        end_time = time.time()
        elapsed = end_time - start_time
        print(f"⏱️ Elapsed time: {elapsed:.2f} seconds")

        # Append to the main list
        self.jobs_enchanced.extend(jobs_enhanced_batch)
        self.response_text += response_text_batch + "\n"

        # Clear the batch for the next iteration
        jobs_batch = []

      return self.jobs_enchanced, self.response_text