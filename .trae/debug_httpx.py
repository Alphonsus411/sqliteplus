import httpx
try:
    from httpx import AsyncClient
    print("AsyncClient imported successfully")
except ImportError as e:
    print(f"Error importing AsyncClient: {e}")
    print(f"httpx dir: {httpx.__file__}")
    print(f"httpx content: {dir(httpx)}")
