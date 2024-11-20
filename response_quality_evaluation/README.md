# lemonade-benchmark
Benchmarking Small Language Models against Large &amp; Enterprise Language Models

Reference: https://github.com/promptfoo/promptfoo


# Step 1: Install promptfoo

sudo apt install npm

npx promptfoo@latest init

# Step 2: Setup api keys in the environment

export OPENAI_API_KEY=<my-api-key>

export ANTHROPIC_API_KEY=<my-api-key>

# Step 3: Run promptfoo

npx promptfoo@latest eval

# Optional: Increase number of parallel threads & max RAM usage

export PROMPTFOO_ASSERTIONS_MAX_CONCURRENCY=10
export NODE_OPTIONS="--max-old-space-size=2048 --optimize-for-size"

# Step 4:  Industry-standard evaluation

The piqa is a great eval used for reasoning capability testing of language models.
Many of the models will fail. The goal is to find ways to 'inject reasoning' through either fine-tuning or prompting.

# Step 5: Using piqa

The goal is to use promptfoo to implement piqa. 
Due to time limitation, we will probably use a small percentage of the whole dataset, i.e. 100 prompts or so

