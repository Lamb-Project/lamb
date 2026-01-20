
from fastapi import FastAPI, Request, Body
import uvicorn
import httpx

app = FastAPI()

OLLAMA_URL = "http://127.0.0.1:11434/api/embeddings"
TIMEOUT = 60.0

@app.post("/api/embed")
async def proxy_embed(request: Request):
    try:
        data = await request.json()
        print(f"Proxy received: {data}")
        
        # Translate input -> prompt
        inputs = data.get("input")
        if isinstance(inputs, str):
            inputs = [inputs]
            
        embeddings = []
        
        async with httpx.AsyncClient() as client:
            for prompt in inputs:
                payload = {
                    "model": "nomic-embed-text:latest", # Ensure model matches what we pulled
                    "prompt": prompt
                }
                
                if "model" in data:
                     payload["model"] = data["model"]
        
                print(f"Proxy forwarding to {OLLAMA_URL}: {payload}")
                
                response = await client.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
                
                if response.status_code == 200:
                    resp_data = response.json()
                    embedding = resp_data.get("embedding", [])
                    embeddings.append(embedding)
                else:
                    # If one fails, fail all? or return partial?
                    # Let's fail for now to be safe
                    return response.json()
            
        new_resp = {
             "embeddings": embeddings # Return list of embeddings
        }
        return new_resp
                
    except Exception as e:
        print(f"Proxy Error: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11435)
