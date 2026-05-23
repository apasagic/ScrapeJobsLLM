import re
import time
import json
import smtplib
import os
from urllib.parse import quote
from email.message import EmailMessage

def request_JSearch_API(conn, headers, query="machine learning remote", num_pages=1):
    encoded_query = quote(query or "machine learning remote")
    conn.request("GET", f"/search-v2?query={encoded_query}&num_pages={num_pages}&date_posted=all", headers=headers)

    res = conn.getresponse()
    raw_data = res.read()

    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSearch response: {e}")
        return []

    jobs = payload.get("data", {}).get("jobs", [])
    formatted_jobs = [format_jsearch_job(job) for job in jobs]
    return formatted_jobs


def parse_fitness_score(value):
    if value is None:
        return 0.0
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    if not match:
        return 0.0
    return max(0.0, min(float(match.group()), 10.0))


def is_senior_role(job):
    text = " ".join(
        str(job.get(key, ""))
        for key in ("title", "seniority", "experience", "description", "tags")
    ).lower()
    senior_terms = ("senior", "sr.", "staff", "principal", "lead", "manager", "architect")
    if any(term in text for term in senior_terms):
        return True
    years = re.findall(r"(\d+)\s*\+?\s*(?:years|yrs)", text)
    return any(int(year) >= 5 for year in years)


def sort_jobs_by_fitness(jobs):
    return sorted(
        jobs,
        key=lambda job: (
            parse_fitness_score(job.get("job_fitness")),
            -float(job.get("distance", 99) or 99),
        ),
        reverse=True,
    )


def format_jsearch_job(job):
    tags = []
    if isinstance(job.get("job_employment_types"), list):
        tags.extend([t for t in job["job_employment_types"] if t])
    if isinstance(job.get("job_benefits_strings"), list):
        tags.extend([t for t in job["job_benefits_strings"] if t])
    if isinstance(job.get("job_salary_string"), str) and job.get("job_salary_string"):
        tags.append(job["job_salary_string"])

    tags = list(dict.fromkeys(tags))

    salary = job.get("job_salary_string") or job.get("job_salary") or "N/A"
    if isinstance(salary, dict):
        salary = salary.get("job_salary_string") or "N/A"

    location = job.get("job_location") or job.get("job_city") or job.get("job_state") or "Remote"
    if job.get("job_is_remote"):
        location = "Remote"

    return {
        "id": job.get("job_id", "N/A"),
        "title": job.get("job_title", "N/A"),
        "link": job.get("job_apply_link", "N/A"),
        "description": job.get("job_description", "N/A"),
        "experience": "N/A",
        "seniority": "N/A",
        "skills": "N/A",
        "tags": ', '.join(tags) if tags else "N/A",
        "salary": salary,
        "location": location,
        "source": job.get("job_publisher", "JSearch"),
        "job_fitness": "N/A",
        "comment": "N/A"
    }


def extract_chroma_entry(results, max_distance=1.7):
    """Flatten vector-search results from storage adapters into job dicts."""
    formatted_results = []

    if not results:
        return formatted_results

    if "results" in results:
        return results["results"]

    ids = results.get("ids") or [[]]
    metadatas = results.get("metadatas") or [[]]
    distances = results.get("distances") or [[]]

    if not metadatas:
        return formatted_results

    for i, metadata in enumerate(metadatas[0]):
        distance = distances[0][i] if distances and distances[0] and i < len(distances[0]) else None

        if distance is not None and distance > max_distance:
            continue

        job = dict(metadata or {})
        if "vector_id" not in job and ids and ids[0] and i < len(ids[0]):
            job["vector_id"] = ids[0][i]
        if distance is not None:
            job["distance"] = distance
        job.setdefault("company", "N/A")
        job.setdefault("url", job.get("link", "N/A"))
        job.setdefault("link", job.get("url", "N/A"))
        formatted_results.append(job)
    
    return formatted_results

def remove_duplicates(jobs):
     # Remove duplicates based on id and source
    seen = set()
    unique_jobs = []

    for job in jobs:
       key = (job.get("id"), job.get("source", ""))
       if key not in seen:
          seen.add(key)
          unique_jobs.append(job)
    
    return unique_jobs

def send_email(to_email, subject, html_content, smtp_from=None, smtp_user=None, smtp_password=None):
    smtp_from = smtp_from or os.environ.get("SMTP_FROM")
    smtp_user = smtp_user or os.environ.get("SMTP_USER")
    smtp_password = smtp_password or os.environ.get("SMTP_PASSWORD")

    if not smtp_from or not smtp_user or not smtp_password:
        raise ValueError("SMTP credentials are required to send email. Provide SMTP_FROM, SMTP_USER, and SMTP_PASSWORD.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_email
    msg.set_content("Your email client does not support HTML.")
    msg.add_alternative(html_content, subtype='html')

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

def count_tokens(text, model="gpt-3.5-turbo"):
    import tiktoken

    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def prompt_llama(llm, prompt):

    # Run inference
    output = llm(prompt, max_tokens=100)

    # Print output
    #print(output["choices"][0]["text"])

    return output["choices"][0]["text"]

def get_openai_client(api_key):
    import openai

    openai.api_key = api_key
    return openai


def summarize_job_search_results(jobs, query, cv_text, client):
    if not jobs:
        return f"No jobs were found for the query '{query}'."

    # If client is None (test mode), return a simple summary
    if client is None:
        job_titles = [job.get('title', 'Unknown') for job in jobs[:3]]
        return f"Found {len(jobs)} jobs for query '{query}'. Top matches: {', '.join(job_titles)}. (Test mode - no LLM summary)"

    prompt = f"""
You are a helpful assistant that summarizes machine learning job search results.

Query: {query}

CV:
{cv_text}

Jobs:
{json.dumps(jobs, indent=2)}

Write a short summary of the top jobs, including the most relevant skills, seniority level, and why these jobs are a good match for the CV provided. Keep it concise and focused.
"""

    response = client.chat.completions.create(
        model="anthropic/claude-sonnet-4",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
    )

    return response.choices[0].message.content


def scrape_job_remoteok(driver,client):
    from bs4 import BeautifulSoup

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
