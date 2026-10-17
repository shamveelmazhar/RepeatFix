import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / "backend" / ".env")

client = OpenAI(base_url=os.getenv("VLLM_BASE_URL"), api_key=os.getenv("VLLM_API_KEY"))

print("Models your key can use:")
for model in client.models.list().data:
    print(" -", model.id)

reply = client.chat.completions.create(
    model=os.getenv("VLLM_MODEL"),
    messages=[{"role": "user", "content": "Say hello in five words."}],
    max_tokens=30,
)
print("\nModel says:", reply.choices[0].message.content)