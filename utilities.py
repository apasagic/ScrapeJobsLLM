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
import smtplib
from email.message import EmailMessage

def extract_chroma_entry(results):
    
    # Structure into list of dicts
    formatted_results = []

    for i in range(len(results['ids'][0])):

        print(results['distances'][0][i])

        if(results["distances"][0][i] > 1.7):  # Adjust threshold as needed
            continue
        formatted_results.append(results["metadatas"][0][i])
    
    return formatted_results

def remove_duplicates(jobs):
     # Remove duplicates based on title + link
    seen = set()
    unique_jobs = []

    for job in jobs:
       key = (job["id"])  # use more fields if needed
       if key not in seen:
          seen.add(key)
          unique_jobs.append(job)
    
    return unique_jobs

def send_email(to_email, subject, html_content):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "your_email@gmail.com"
    msg["To"] = to_email
    msg.set_content("Your email client does not support HTML.")
    msg.add_alternative(html_content, subtype='html')

    # Send using Gmail SMTP
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login("your_email@gmail.com", "your_app_password")  # Use App Password
        smtp.send_message(msg)

def count_tokens(text, model="gpt-3.5-turbo"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def prompt_llama(llm, prompt):

    # Run inference
    output = llm(prompt, max_tokens=100)

    # Print output
    #print(output["choices"][0]["text"])

    return output["choices"][0]["text"]

def get_openai_client(api_key):
    openai.api_key = api_key
    return openai

def scrape_job_remoteok(driver,client):
    url = "https://remoteok.io/remote-machine-learning-jobs"
    driver.get(url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # Step 2: Extract job data
    job_cards = soup.find_all("tr", id=re.compile(r"^job.*"))
    print(f"Found {len(job_cards)} job entries")

    jobs = []
    #jobs_query_text = ""

    for card in job_cards:
       try:
           tr_id = re.search(r"job-(\d+)", card.get("id", "")).group(1)
           job_desc_card = soup.find("tr", class_=re.compile(f"expand-{tr_id}"))

           description_tag = job_desc_card.find(attrs={"itemprop": "description"})

           if description_tag:
             description = description_tag.get_text(strip=True)
           else:
             description = "No description found."  
             print("No description found.")

           title = card.find("h2", itemprop="title").get_text(strip=True)
           link = "https://remoteok.io" + card.find("a", href=True)["href"]

           tags = [tag.get_text(strip=True) for tag in card.find_all("div", class_="tag")]
           salary_tag = card.find("div", class_="salary")
           salary = salary_tag.get_text(strip=True) if salary_tag else "N/A"

           location_tag = card.find("div", class_="location")
           location = location_tag.get_text(strip=True) if location_tag else "Remote"

           jobs.append({
               "id": tr_id,
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
            })

           #jobs_query_text += f"Title: {title}\nDescription: {description}\nTags: {', '.join(tags)}\nSalary: {salary}\nLocation: {location}\nLink: {link}\n\n"
       except Exception as e:
           print(f"Skipped one job due to error: {e}")

    return jobs

def generate_html_report(jobs, summary_text):
    """
    Generate HTML containing a summary and a table of job listings.
    """
    # Define table headers
    headers = ["Id","Title", "Link", "Description", "Experience", "Seniority","Skills", "Tags", "Salary", "Location", "Source", "Job Fitness","Comment"]

    # Start HTML
    html = """
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h2 {{ color: #333; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background-color: #f2f2f2; }}
        tr:nth-child(even) {{ background-color: #fafafa; }}
        .summary {{ background: #eef; padding: 15px; border: 1px solid #ccd; border-radius: 5px; }}
        a {{ color: #0645ad; text-decoration: none; }}
    </style>
    <title>Job Analysis Report</title>
</head>
<body>
    <h2>📝 Job Summary</h2>
    <div class="summary">{summary}</div>

    <h2>📋 Job Listings ({count} jobs)</h2>
    <table>
        <thead>
            <tr>{header_row}</tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
</body>
</html>
"""

    # Create header row
    header_row = ''.join(f"<th>{h}</th>" for h in headers)

    # Create rows
    table_rows = ""
    for job in jobs:
        row = "<tr>"
        for h in headers:
            key = h.lower().replace(" ", "_")
            value = job.get(key, "N/A")
            if h.lower() == "link" and value != "N/A":
                value = f'<a href="{value}" target="_blank">{value}</a>'
            row += f"<td>{value}</td>"
        row += "</tr>"
        table_rows += row

    # Final HTML
    final_html = html.format(
        summary=summary_text.replace("\n", "<br>"),
        count=len(jobs),
        header_row=header_row,
        table_rows=table_rows
    )

    return final_html