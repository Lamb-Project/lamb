import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=9090, 
        reload=True,
        reload_excludes=["static/*", "static/**/*", "data/*", "data/**/*"]
    )
