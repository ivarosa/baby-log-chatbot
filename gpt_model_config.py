import os
import openai

# Get model from env (default: gpt-4o)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

def estimate_calories_openai(food_log: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "API key for OpenAI not set."
    prompt = (
        "Tolong hitung estimasi total kalori dari makanan berikut untuk bayi.\n"
        "Sebutkan juga rincian kalori per bahan. Jawab singkat dengan format berikut:\n"
        "[nama bahan]: [kalori] kkal\n"
        "Total: [total kalori] kkal\n\n"
        f"Makanan: {food_log}"
    )
    try:
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Kamu adalah ahli nutrisi makanan bayi dan MPASI."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=256,
            temperature=0.2,
            api_key=api_key
        )
        answer = response['choices'][0]['message']['content']
        return answer
    except Exception as e:
        return f"Terjadi kesalahan saat menghitung kalori dengan OpenAI: {e}"
