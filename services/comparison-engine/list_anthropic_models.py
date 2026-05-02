import asyncio
import os
from comparison_engine.runner import _fetch_model_metas
from anthropic import AsyncAnthropic

async def main():
    model_ids = ["claude-4-7-opus-20260416"] # Just to get one record to extract the key
    metas = await _fetch_model_metas(model_ids)
    
    key = None
    for m in metas.values():
        if m.get("provider") == "Anthropic":
            key = m.get("api_config", {}).get("api_key")
            if key: break
            
    if not key:
        print("ERROR: Could not find Anthropic API key in DB")
        return

    print(f"Using key: {key[:8]}...")
    client = AsyncAnthropic(api_key=key)
    try:
        models = await client.models.list()
        print("\n=== Available Anthropic Models ===")
        for m in models.data:
            print(f"ID: {m.id}")
        print("==================================\n")
    except Exception as e:
        print(f"FAILED to list models: {e}")

if __name__ == "__main__":
    asyncio.run(main())
