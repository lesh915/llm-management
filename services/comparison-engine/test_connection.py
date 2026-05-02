import asyncio
import os
from comparison_engine.runner import _fetch_model_metas, preflight_check

async def main():
    model_ids = ["gpt-4o-mini", "gemini-2.0-flash", "claude-haiku-3-5"]
    print(f"Fetching metas for {model_ids}...")
    metas = await _fetch_model_metas(model_ids)
    for k, v in metas.items():
        print(f"Found meta for {k}: has api_config? {'api_config' in v}, has api_key? {'api_key' in v.get('api_config', {})}")
        if 'api_key' in v.get('api_config', {}):
            print(f"  api_key value: {v['api_config']['api_key']}")

    print("\nRunning preflight check...")
    try:
        await preflight_check(model_ids, metas)
        print("Success! All models are reachable.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
