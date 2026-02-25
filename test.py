from llama_cpp import Llama
import yaml

# Load configuration
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Load the model from config
llm = Llama(
    model_path=config['paths']['model'],
    n_ctx=2048,         # Context size (adjust as needed)
    n_threads=4,        # Number of CPU threads (or GPU config if built that way)
    verbose=True
)

# Simple prompt
prompt = "Summarize the following job posting:\nSenior ML Engineer with experience in NLP and PyTorch, remote position, $150k salary."

# Run inference
output = llm(prompt, max_tokens=100)

# Print output
print(output["choices"][0]["text"])
