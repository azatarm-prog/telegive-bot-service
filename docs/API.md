# Bot Service API Documentation

## Overview

The Telegive Bot Service provides REST API endpoints for managing Telegram bot operations, webhook processing, and inter-service communication.

## Authentication

All API endpoints (except webhooks and health checks) require authentication via Bearer token:

```
Authorization: Bearer <your_auth_token>
```

## Base URL

```
https://your-bot-service-domain.com
```

## Webhook Endpoints

### Receive Telegram Webhook

Processes incoming Telegram webhook updates.

**Endpoint:** `POST /webhook/<bot_token>`

**Parameters:**
- `bot_token` (path): Telegram bot token

**Request Body:**
```json
{
  "update_id": 123456,
  "message": {
    "message_id": 1,
    "from": {
      "id": 12345,
      "first_name": "User"
    },
    "chat": {
      "id": 12345,
      "type": "private"
    },
    "text": "/start"
  }
}
```

**Response:**
- `200 OK`: Webhook processed successfully
- `400 Bad Request`: Invalid request format

### Get Webhook Information

Retrieves current webhook configuration for a bot.

**Endpoint:** `GET /webhook/<bot_token>`

**Response:**
```json
{
  "success": true,
  "webhook_url": "https://example.com/webhook/token",
  "has_custom_certificate": false,
  "pending_update_count": 0
}
```

### Set Webhook URL

Configures webhook URL for a bot.

**Endpoint:** `POST /webhook/<bot_token>/set`

**Request Body:**
```json
{
  "webhook_url": "https://your-domain.com/webhook/bot_token"
}
```

**Response:**
```json
{
  "success": true,
  "description": "Webhook was set"
}
```

### Delete Webhook

Removes webhook configuration for a bot.

**Endpoint:** `POST /webhook/<bot_token>/delete`

**Response:**
```json
{
  "success": true,
  "description": "Webhook was deleted"
}
```

## Bot API Endpoints

### Post Giveaway Message

Posts a giveaway message to a Telegram channel with participation button.

**Endpoint:** `POST /post-giveaway`

**Headers:**
```
Authorization: Bearer <auth_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "account_id": 1,
  "giveaway_data": {
    "id": 100,
    "channel_id": -100123456789,
    "main_body": "🎁 Win amazing prizes!\n\nClick PARTICIPATE to join!",
    "media_file_id": 123
  }
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 123,
  "channel_id": -100123456789,
  "posted_at": "2024-01-01T00:00:00Z",
  "inline_keyboard_attached": true
}
```

**Error Responses:**
- `400 Bad Request`: Missing required fields
- `401 Unauthorized`: Missing or invalid auth token
- `500 Internal Server Error`: Bot token or posting error

### Post Conclusion Message

Posts a conclusion message with VIEW RESULTS button.

**Endpoint:** `POST /post-conclusion`

**Request Body:**
```json
{
  "account_id": 1,
  "giveaway_id": 100,
  "channel_id": -100123456789,
  "conclusion_message": "🎊 Giveaway concluded! Check if you won!",
  "result_token": "result_token_123"
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 124,
  "channel_id": -100123456789,
  "posted_at": "2024-01-01T00:00:00Z",
  "view_results_button_attached": true
}
```

### Send Bulk Messages

Sends messages to multiple participants (winners/losers).

**Endpoint:** `POST /send-bulk-messages`

**Request Body:**
```json
{
  "account_id": 1,
  "giveaway_id": 100,
  "participants": [
    {
      "user_id": 12345,
      "is_winner": true
    },
    {
      "user_id": 67890,
      "is_winner": false
    }
  ],
  "winner_message": "🎊 Congratulations! You won!",
  "loser_message": "Thank you for participating! Better luck next time!"
}
```

**Response:**
```json
{
  "success": true,
  "total_recipients": 2,
  "messages_sent": 2,
  "delivery_failures": 0,
  "failed_deliveries": []
}
```

### Send Direct Message

Sends a direct message to a specific user.

**Endpoint:** `POST /send-dm`

**Request Body:**
```json
{
  "account_id": 1,
  "user_id": 12345,
  "message": "Hello! This is a direct message.",
  "parse_mode": "HTML",
  "reply_markup": {
    "inline_keyboard": [[
      {
        "text": "Button",
        "callback_data": "action:data"
      }
    ]]
  }
}
```

**Response:**
```json
{
  "success": true,
  "message_id": 125,
  "delivered_at": "2024-01-01T00:00:00Z"
}
```

### Get User Information

Retrieves user information from Telegram.

**Endpoint:** `GET /user-info/<user_id>`

**Response:**
```json
{
  "success": true,
  "user_info": {
    "id": 12345,
    "username": "testuser",
    "first_name": "Test",
    "last_name": "User",
    "is_bot": false,
    "language_code": "en"
  }
}
```

### Check Channel Membership

Verifies if a user is a member of a specific channel.

**Endpoint:** `POST /check-membership`

**Request Body:**
```json
{
  "bot_token": "bot_token_here",
  "channel_id": -100123456789,
  "user_id": 12345
}
```

**Response:**
```json
{
  "success": true,
  "is_member": true,
  "membership_status": "member",
  "checked_at": "2024-01-01T00:00:00Z"
}
```

### Get Delivery Status

Retrieves message delivery statistics for a giveaway.

**Endpoint:** `GET /delivery-status/<giveaway_id>`

**Response:**
```json
{
  "success": true,
  "delivery_stats": {
    "total_participants": 100,
    "messages_sent": 95,
    "delivery_failed": 3,
    "users_blocked_bot": 2,
    "pending_delivery": 0
  },
  "failed_deliveries": [
    {
      "user_id": 12345,
      "error_code": "USER_BLOCKED_BOT",
      "last_attempt": "2024-01-01T00:00:00Z"
    }
  ]
}
```

## Health Check Endpoints

### Main Health Check

Provides overall service health status.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "service": "bot-service",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "database": "connected",
  "telegram_api": "accessible",
  "webhook_status": "configured",
  "external_services": {
    "auth_service": "accessible",
    "channel_service": "accessible",
    "telegive_service": "accessible",
    "participant_service": "accessible",
    "media_service": "accessible"
  }
}
```

**Status Codes:**
- `200 OK`: Service is healthy
- `503 Service Unavailable`: Service is unhealthy

### Database Health Check

Checks database connectivity and provides statistics.

**Endpoint:** `GET /health/database`

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "statistics": {
    "bot_interactions": 1000,
    "message_deliveries": 500,
    "webhook_processes": 2000
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### External Services Health Check

Checks connectivity to external services.

**Endpoint:** `GET /health/services`

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "auth_service": "accessible",
    "channel_service": "accessible",
    "telegive_service": "accessible",
    "participant_service": "accessible",
    "media_service": "accessible"
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Telegram API Health Check

Checks Telegram API accessibility.

**Endpoint:** `GET /health/telegram`

**Response:**
```json
{
  "status": "healthy",
  "telegram_api": "accessible",
  "api_base": "https://api.telegram.org",
  "response_code": 401,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Service Status

Provides detailed service status and statistics.

**Endpoint:** `GET /status`

**Response:**
```json
{
  "service": "bot-service",
  "version": "1.0.0",
  "uptime": "5 days, 3 hours",
  "configuration": {
    "service_port": 5000,
    "webhook_base_url": "https://bot.example.com",
    "max_message_length": 4096,
    "bulk_message_batch_size": 50,
    "message_retry_attempts": 3
  },
  "statistics": {
    "today": {
      "interactions": 150,
      "message_deliveries": 75,
      "webhook_processes": 200,
      "failed_interactions": 5,
      "failed_deliveries": 2
    },
    "error_rates": {
      "interaction_error_rate": 3.33,
      "delivery_error_rate": 2.67
    }
  },
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Error Codes

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_BOT_TOKEN_FORMAT` | Bot token format is invalid |
| `INVALID_JSON` | Request body is not valid JSON |
| `EMPTY_UPDATE_DATA` | Webhook update data is empty |
| `MISSING_AUTH_TOKEN` | Authorization header is missing |
| `MISSING_REQUIRED_FIELDS` | Required fields are missing from request |
| `INVALID_GIVEAWAY_ID` | Giveaway ID is invalid or missing |
| `USER_BLOCKED_BOT` | User has blocked the bot |
| `CHAT_NOT_FOUND` | Chat or user not found |
| `MESSAGE_NOT_FOUND` | Message to edit not found |
| `RATE_LIMITED` | Too many requests |
| `SERVICE_UNAVAILABLE` | External service is unavailable |

### Error Response Format

```json
{
  "success": false,
  "error": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Rate Limiting

- Webhook endpoints: No rate limiting (handled by Telegram)
- API endpoints: 100 requests per minute per IP
- Bulk operations: 10 requests per minute per account

## Webhook Security

- Bot token validation in URL path
- Request signature verification (optional)
- IP whitelist support (optional)
- HTTPS required for production

## Best Practices

1. **Error Handling**: Always check the `success` field in responses
2. **Retries**: Implement exponential backoff for failed requests
3. **Timeouts**: Set appropriate timeouts for API calls
4. **Logging**: Log all API interactions for debugging
5. **Monitoring**: Monitor health endpoints regularly

