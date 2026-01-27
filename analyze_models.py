
import requests
import json
import os
import sys

def analyze_models():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Fetching models...", flush=True)
    report_lines = []

    try:
        response = requests.get("https://openrouter.ai/api/v1/models")
        response.raise_for_status()
        data = response.json()

        models = data.get("data", [])
        report_lines.append(f"Total models found: {len(models)}")

        # Categories to find
        free_models = []
        cheap_high_perf = []

        for m in models:
            pid = m.get("pricing", {})
            prompt = float(pid.get("prompt", 0))
            completion = float(pid.get("completion", 0))

            # Check for free
            if prompt == 0 and completion == 0:
                free_models.append(m)

            # Check for cheap but good (< $0.50/1M is very cheap)
            elif prompt <= 0.0000005:
                cheap_high_perf.append(m)

        report_lines.append("\n--- TOP FREE MODELS ---")
        interesting_keywords = ["gemini", "llama", "deepseek", "mistral", "qwen", "liquid", "nvidia"]

        for m in free_models:
            name = m.get("name", "").lower()
            if any(k in name for k in interesting_keywords):
                report_lines.append(f"- {m['id']} ({m['name']})")

        report_lines.append("\n--- TOP CHEAP MODELS (<$0.5/1M) ---")
        for m in cheap_high_perf:
             name = m.get("name", "").lower()
             if any(k in name for k in interesting_keywords):
                 cost = float(m['pricing']['prompt'])*1000000
                 report_lines.append(f"- {m['id']} : Prompt ${cost:.2f}/1M")

        with open("models_report.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        print("Report written to models_report.txt", flush=True)

    except Exception as e:
        with open("models_report.txt", "w", encoding="utf-8") as f:
            f.write(f"Error: {e}")
        print(f"Error: {e}", flush=True)

if __name__ == "__main__":
    analyze_models()
