# tRPC Compatibility Layer Implementation

## Overview

This implementation adds a tRPC compatibility layer to the FastAPI ingestion spine, allowing the Ops Console frontend to communicate with the backend using tRPC endpoints while maintaining all existing REST functionality.

## Problem Solved

The Ops Console frontend uses tRPC to communicate with the backend, but the ingestion spine is built with FastAPI and exposes REST endpoints. This caused 404 errors when the frontend tried to call tRPC endpoints like `/trpc/ingestion.createBatch`.

## Solution

Added a tRPC adapter layer that:
1. Exposes endpoints at `/trpc/*` path
2. Accepts tRPC-formatted requests (both POST and GET)
3. Translates to existing FastAPI endpoints
4. Returns tRPC-formatted responses

## Implementation Details

### Files Created

1. **`/workers/ingestion_spine/trpc_adapter.py`**
   - Main adapter implementation
   - 6 tRPC endpoints (12 routes including GET/POST)
   - Request/response format translation
   - Error handling

2. **`/tests/test_trpc_adapter.py`**
   - Comprehensive test suite
   - Tests all endpoints
   - Tests error cases
   - Tests both GET and POST methods

### Files Modified

1. **`/workers/ingestion_spine/main.py`**
   - Added tRPC router import
   - Included tRPC router in FastAPI app

## Endpoints

| tRPC Endpoint | FastAPI Endpoint | Description |
|---------------|------------------|-------------|
| `/trpc/ingestion.createBatch` | `POST /imports/batch` | Create a new import batch |
| `/trpc/ingestion.registerFiles` | `POST /imports/{batch_id}/files` | Register files for a batch |
| `/trpc/ingestion.parseBatch` | `POST /imports/{batch_id}/parse` | Parse batch files |
| `/trpc/ingestion.getBatchStatus` | `GET /imports/{batch_id}` | Get batch status |
| `/trpc/ingestion.listRaces` | `GET /races/{import_date}` | List races for a date |
| `/trpc/ingestion.getRaceDetails` | `GET /races/{race_id}/details` | Get race details |

## Request/Response Format

### tRPC Request Format

**POST:**
```json
{
  "input": {
    "batch_id": "uuid",
    "import_date": "2026-01-06"
  }
}
```

**GET:**
```
?input={"batch_id":"uuid","import_date":"2026-01-06"}
```

### tRPC Response Format

**Success:**
```json
{
  "result": {
    "data": {
      "batch_id": "uuid",
      "status": "uploaded",
      "message": "Batch created"
    }
  }
}
```

**Error:**
```json
{
  "error": {
    "message": "Error description",
    "code": "INTERNAL_SERVER_ERROR"
  }
}
```

## Key Features

1. **Dual Method Support**: All endpoints support both GET and POST requests (tRPC spec)
2. **Consistent Serialization**: Smart serialization handles Pydantic v1 and v2 models
3. **Proper Error Handling**: Errors are formatted according to tRPC spec
4. **No Breaking Changes**: Existing REST endpoints continue to work
5. **Type Safe**: Reuses existing Pydantic models from FastAPI

## Testing

### Validation Tests
- Helper functions work correctly
- All routes properly registered
- Main app integration successful

### Integration Tests
- Request/response format translation
- Data serialization (simple and nested)
- Error handling
- Both GET and POST methods

### Security
- CodeQL analysis: ✅ No security issues found
- No SQL injection risks (uses existing validated endpoints)
- No XSS risks (JSON responses only)
- No authentication bypass (uses existing auth if any)

## Code Quality Improvements

Based on code review feedback:
1. Fixed GET request parsing to support query parameters
2. Added consistent `serialize_result()` helper
3. Fixed mutation issue (changed `pop()` to `get()`)
4. All endpoints use consistent approach
5. Handles both Pydantic v1 and v2

## Usage Examples

### Frontend (tRPC Client)

```typescript
// Create a batch
const result = await trpc.ingestion.createBatch.mutate({
  import_date: "2026-01-06",
  source: "racing_post"
});

// Get batch status
const status = await trpc.ingestion.getBatchStatus.query({
  batch_id: "uuid"
});

// List races
const races = await trpc.ingestion.listRaces.query({
  import_date: "2026-01-06"
});
```

### Direct HTTP Requests

```bash
# POST request
curl -X POST http://localhost:8000/trpc/ingestion.createBatch \
  -H "Content-Type: application/json" \
  -d '{"input": {"import_date": "2026-01-06", "source": "racing_post"}}'

# GET request
curl "http://localhost:8000/trpc/ingestion.listRaces?input=%7B%22import_date%22%3A%222026-01-06%22%7D"
```

## Impact

### Before
- Frontend: ❌ 404 errors on `/trpc/*` endpoints
- Backend: ✅ Only REST endpoints available

### After
- Frontend: ✅ Can communicate via tRPC
- Backend: ✅ Both REST and tRPC endpoints work
- Integration: ✅ No changes needed to existing code

## Maintenance Notes

### Adding New Endpoints

To add a new tRPC endpoint:

1. Add the endpoint to `/workers/ingestion_spine/trpc_adapter.py`:
```python
@router.post("/ingestion.newEndpoint")
@router.get("/ingestion.newEndpoint")
async def trpc_new_endpoint(request: Request):
    try:
        input_data = await parse_trpc_request(request)
        # Extract parameters
        param = input_data.get("param")
        
        # Call existing endpoint
        from .main import existing_endpoint
        result = await existing_endpoint(param)
        
        # Return tRPC format
        return format_trpc_response(serialize_result(result))
    except HTTPException as e:
        return format_trpc_error(e.detail, "BAD_REQUEST")
    except Exception as e:
        logger.error(f"tRPC error: {e}")
        return format_trpc_error(str(e), "INTERNAL_SERVER_ERROR")
```

2. Add tests to `/tests/test_trpc_adapter.py`

3. No changes needed to `main.py` (router is already included)

## Performance

- **Minimal Overhead**: Direct function calls to existing endpoints
- **No Extra Dependencies**: Uses FastAPI's native features
- **Stateless**: No session management overhead
- **Async**: Full async/await support maintained

## Monitoring

The adapter logs all requests:
- Request parsing errors
- Endpoint-specific errors
- Response format issues

Example log output:
```
2026-01-06 17:28:57,373 - workers.ingestion_spine.main - INFO - Creating batch for date: 2026-01-06
2026-01-06 17:28:57,374 - workers.ingestion_spine.main - INFO - ✅ Batch created: test-batch-123
```

## Troubleshooting

### Frontend Still Getting 404s
- Verify the backend is running
- Check the URL path includes `/trpc/`
- Verify the endpoint name matches exactly

### Invalid Input Error
- Check the input is wrapped in `{"input": {...}}`
- Verify all required fields are present
- Check date format is ISO 8601 (YYYY-MM-DD)

### Serialization Error
- Verify the underlying FastAPI endpoint returns a serializable response
- Check if the model uses Pydantic v1 or v2
- The `serialize_result()` helper handles both versions

## Future Enhancements

Possible improvements:
1. Add request validation middleware
2. Add response caching
3. Add request rate limiting
4. Add detailed request/response logging
5. Add OpenAPI/tRPC schema generation

## References

- [tRPC Documentation](https://trpc.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- Original issue: Frontend 404 errors on tRPC endpoints
