# API Authentication & Key Management

Lahuta uses a multi-user API key system to secure model access and track usage.

## Key Formats
- **Master Key**: Defined in your `.env` file as `API_KEY`. This provides full admin access to all endpoints.
- **User Keys**: Formatted as `lh_[random_string]`. These are generated per user and stored securely (hashed) in the database.

## User Registration
To generate a new set of keys, you must first register a user:

```bash
curl -X POST http://localhost:8000/auth/register \
     -H "Content-Type: application/json" \
     -d '{"username": "stiven"}'
```

**Response:**
```json
{
  "status": "success",
  "username": "stiven",
  "api_key": "lh_abc123..."
}
```

> [!IMPORTANT]
> The API key is only shown once at registration. Store it securely!

## Using the API Key
Include the key in the `x-api-key` header for all requests:

```bash
curl -X POST http://localhost:8000/analyze \
     -H "x-api-key: lh_your_key_here" \
     -H "Content-Type: application/json" \
     -d '{
       "model_id": "albanian_analysis",
       "text": "..."
     }'
```

## Managing Multiple Keys
An authenticated user can generate additional keys for different applications:

```bash
curl -X POST http://localhost:8000/auth/keys \
     -H "x-api-key: lh_existing_key" \
     -H "Content-Type: application/json" \
     -d '{"name": "mobile_app_key"}'
```

## Security Implementation
- Keys are hashed using **SHA-256** before storage.
- The server tracks `last_used_at` for every key.
- If no `API_KEY` is set in the environment, the server runs in **Development Mode** (allowing anonymous access), but this is not recommended for production.
