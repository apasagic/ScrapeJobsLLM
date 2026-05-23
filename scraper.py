import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import openai
import httpx
import json
import tempfile
from utilities import request_JSearch_API, scrape_job_remoteok

DEAD_PROXY_MARKER = "127.0.0.1:9"


def clear_dead_proxy_env():
    """Remove the local dead proxy that breaks OpenRouter and webdriver-manager."""
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        if DEAD_PROXY_MARKER in (os.environ.get(key) or ""):
            os.environ.pop(key, None)


class JobScraper:
    def __init__(self, config, conn, headers, my_cv, batch_size=10):
        clear_dead_proxy_env()
        
        self.config = config
        self.conn = conn
        self.headers = headers
        
        # Check if using test mode FIRST - skip driver if so
        rapidapi_key = headers.get('x-rapidapi-key', '')
        if rapidapi_key == 'test-key-for-testing':
            self.driver = None
            self.client = None
            self.download_counter = 0
            self.scraping_done = False
            self.response_text = ""
            self.jobs = []
            self.jobs_enchanced = []
            self.my_cv = my_cv
            self.batch_size = batch_size
            return
        
        # Normal mode. Keep browser/LLM optional so API-only searches still work.
        self.driver = None
        openrouter_key = os.environ.get("OPENROUTER_KEY") or config['api'].get('openrouter_key')
        self.client = None
        if openrouter_key:
            self.client = openai.OpenAI(
                    api_key=openrouter_key,
                    base_url=config['api']['openrouter_url'],
                    http_client=httpx.Client(trust_env=False),
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
        chrome_options.add_argument(f"--user-data-dir={tempfile.mkdtemp(prefix='scrapejobs_chrome_')}")
        chrome_options.add_argument("--remote-debugging-port=0")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-software-rasterizer")
        # Let webdriver-manager choose a driver that matches the installed Chrome.
        # The config chromedriver path can become stale after Chrome auto-updates.
        service = Service(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.get('http://google.com/')

        return self.driver

    def get_openai_client(self):
        openrouter_key = os.environ.get("OPENROUTER_KEY") or self.config['api'].get('openrouter_key')
        if not openrouter_key:
            raise ValueError("OpenRouter API key is not set. Set OPENROUTER_KEY environment variable or api.openrouter_key in config.yaml")
        openai.api_key = openrouter_key
        return openai
    
    def scrape_job(self, website, query=None):

        # Check if using test mode
        rapidapi_key = self.headers.get('x-rapidapi-key', '')
        if rapidapi_key == 'test-key-for-testing':
            return self.get_mock_jobs(website)

        if website == "remoteok":
           if self.driver is None:
               self.driver = self.get_driver()
           jobs =  scrape_job_remoteok(self.driver, self.client)
           return self.compress_description(jobs, self.my_cv, self.client)
        elif website == "JSearch":
           jobs = request_JSearch_API(self.conn, self.headers, query=query)
           return self.compress_description(jobs, self.my_cv, self.client)

    def get_mock_jobs(self, website):
        """Return mock job data for testing"""
        mock_jobs = [
            {
                "id": f"mock-{website}-1",
                "source": website,
                "title": "Senior Machine Learning Engineer",
                "company": "Tech Corp",
                "location": "Remote",
                "description": "We are looking for a Senior ML Engineer with 5+ years of experience in Python, TensorFlow, and NLP. You will work on cutting-edge AI projects.",
                "url": "https://example.com/job1",
                "tags": ["Python", "TensorFlow", "NLP", "Remote"],
                "seniority": "Senior",
                "experience": "5+ years",
                "skills": "Python, TensorFlow, NLP, Machine Learning",
                "salary": "$120k - $150k"
            },
            {
                "id": f"mock-{website}-2",
                "source": website,
                "title": "Data Scientist",
                "company": "Data Inc",
                "location": "San Francisco",
                "description": "Join our team as a Data Scientist. Experience with scikit-learn, pandas, and statistical modeling required.",
                "url": "https://example.com/job2",
                "tags": ["Python", "scikit-learn", "pandas", "Statistics"],
                "seniority": "Mid-level",
                "experience": "3-5 years",
                "skills": "Python, scikit-learn, pandas, Statistics",
                "salary": "$90k - $120k"
            },
            {
                "id": f"mock-{website}-3",
                "source": website,
                "title": "AI Research Engineer",
                "company": "AI Labs",
                "location": "New York",
                "description": "Research position focusing on deep learning and computer vision. PhD preferred but not required.",
                "url": "https://example.com/job3",
                "tags": ["Deep Learning", "Computer Vision", "PyTorch", "Research"],
                "seniority": "Senior",
                "experience": "5+ years",
                "skills": "PyTorch, Deep Learning, Computer Vision, Research",
                "salary": "$130k - $160k"
            }
        ]
        return mock_jobs, "Mock job data for testing"

    def compress_description(self,jobs,my_cv,client):
      
      # If client is None (test mode), return jobs as-is
      if client is None:
          return jobs, "Mock data - no LLM processing"
      
      jobs_batch = []

      def enhance_batch(batch):
        if not batch:
            return

        print(f"Processing batch of {len(batch)} jobs...")
      
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

        user_prompt = f"""CV:\n{my_cv}\n\nJobs:\n{json.dumps(batch, indent=2)}"""

        start_time = time.time()

        try:
            response = client.chat.completions.create(
            model=self.config.get("api", {}).get("openrouter_model", "anthropic/claude-sonnet-4"),
            messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
            )
        except Exception as e:
            print(f"LLM enrichment failed; keeping original scraped jobs. Error: {e}")
            self.jobs_enchanced.extend(batch)
            self.response_text += f"LLM enrichment failed: {e}\n"
            return

        # Extract result
        response_text_batch = response.choices[0].message.content

        # Remove Markdown formatting
        if response_text_batch.startswith("```json"):
           response_text_batch = response_text_batch.strip("```json").strip("```").strip()

        # Parse JSON from response
        try:
           jobs_enhanced_batch = json.loads(response_text_batch)
        except json.JSONDecodeError:
           print("Failed to parse JSON from LLM response.")
           jobs_enhanced_batch = batch

        if not isinstance(jobs_enhanced_batch, list) or len(jobs_enhanced_batch) == 0:
           print("LLM returned no jobs; keeping original scraped jobs.")
           jobs_enhanced_batch = batch

        end_time = time.time()
        elapsed = end_time - start_time
        print(f"Elapsed time: {elapsed:.2f} seconds")

        # Append to the main list
        self.jobs_enchanced.extend(jobs_enhanced_batch)
        self.response_text += response_text_batch + "\n"

      for job in jobs:
        jobs_batch.append(job)

        if len(jobs_batch) < self.batch_size:
            continue

        enhance_batch(jobs_batch)

        # Clear the batch for the next iteration
        jobs_batch = []

      enhance_batch(jobs_batch)

      return self.jobs_enchanced, self.response_text
