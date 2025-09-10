# Telegive Bot Service

A comprehensive Telegram bot service for managing giveaway interactions, user participation, and automated messaging within the Telegive ecosystem.

## Features

- **Webhook Processing**: Handles incoming Telegram webhook updates
- **User Interaction Management**: Processes messages and callback queries
- **Giveaway Participation**: Manages user participation in giveaways with captcha and subscription verification
- **Automated Messaging**: Sends bulk messages to participants with retry mechanisms
- **Multi-Service Integration**: Communicates with auth, channel, giveaway, participant, and media services
- **Background Tasks**: Handles message retries and data cleanup
- **Comprehensive Logging**: Tracks all interactions and operations
- **Health Monitoring**: Provides health checks and service status

## Architecture

The bot service is built with Flask and follows a modular architecture:

```
telegive-bot/
├── app.py                 # Main Flask application
├── config/               # Configuration settings
├── models/               # Database models
├── handlers/             # Message and callback handlers
├── routes/               # API routes
├── services/             # External service integrations
├── utils/                # Utility functions
├── tasks/                # Background tasks
└── tests/                # Test suite
```

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Docker (optional)

### Environment Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd telegive-bot
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Initialize database:
```bash
python database_init.py
```

6. Run the application:
```bash
python app.py
```

### Docker Deployment

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

2. Check service health:
```bash
curl http://localhost:5000/health
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Flask environment | `development` |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `TELEGIVE_AUTH_URL` | Auth service URL | Required |
| `TELEGIVE_CHANNEL_URL` | Channel service URL | Required |
| `TELEGIVE_GIVEAWAY_URL` | Giveaway service URL | Required |
| `TELEGIVE_PARTICIPANT_URL` | Participant service URL | Required |
| `TELEGIVE_MEDIA_URL` | Media service URL | Required |
| `WEBHOOK_BASE_URL` | Base URL for webhooks | Required |
| `SERVICE_PORT` | Service port | `5000` |
| `MAX_MESSAGE_LENGTH` | Maximum message length | `4096` |
| `BULK_MESSAGE_BATCH_SIZE` | Bulk message batch size | `50` |
| `MESSAGE_RETRY_ATTEMPTS` | Message retry attempts | `3` |

### Database Configuration

The service uses PostgreSQL with SQLAlchemy ORM. Database models include:

- `BotInteraction`: Logs all user interactions
- `MessageDeliveryLog`: Tracks message delivery status
- `WebhookProcessingLog`: Records webhook processing

## API Endpoints

### Webhook Endpoints

- `POST /webhook/<bot_token>` - Receive Telegram webhooks
- `GET /webhook/<bot_token>` - Get webhook information
- `POST /webhook/<bot_token>/set` - Set webhook URL
- `POST /webhook/<bot_token>/delete` - Delete webhook

### Bot API Endpoints

- `POST /post-giveaway` - Post giveaway message to channel
- `POST /post-conclusion` - Post conclusion message with results button
- `POST /send-bulk-messages` - Send bulk messages to participants
- `POST /send-dm` - Send direct message to user
- `GET /user-info/<user_id>` - Get user information
- `POST /check-membership` - Check channel membership
- `GET /delivery-status/<giveaway_id>` - Get message delivery status

### Health Endpoints

- `GET /health` - Main health check
- `GET /health/database` - Database health check
- `GET /health/services` - External services health check
- `GET /health/telegram` - Telegram API health check
- `GET /status` - Detailed service status

## User Interactions

### Message Handling

The bot handles various message types:

- **Commands**: `/start`, `/help`, `/cancel`
- **Captcha Responses**: Math problem answers
- **General Messages**: Guidance for participation

### Callback Query Handling

Supports inline keyboard interactions:

- **Participate**: `participate:<giveaway_id>`
- **View Results**: `view_results:<result_token>`
- **Captcha**: `captcha:<giveaway_id>:<option>:<answer>`

## Background Tasks

### Message Retry Service

Automatically retries failed message deliveries:

- Configurable retry intervals (5min, 15min, 1hour)
- Maximum retry attempts (3 by default)
- Excludes permanently failed cases (user blocked bot)

### Cleanup Service

Periodic cleanup of old data:

- **Daily**: Webhook logs (7 days), bot interactions (30 days)
- **Weekly**: Message delivery logs (90 days)
- **Hourly**: Temporary files, stuck processes

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
```

### Test Structure

- **Unit Tests**: Individual component testing
- **Integration Tests**: Service interaction testing
- **End-to-End Tests**: Complete workflow testing

## Deployment

### Railway Deployment

1. Configure `railway.json` for Railway platform
2. Set environment variables in Railway dashboard
3. Deploy using Railway CLI or GitHub integration

### Manual Deployment

1. Set up production environment
2. Configure reverse proxy (nginx)
3. Set up SSL certificates
4. Configure monitoring and logging

### Environment-Specific Configurations

- **Development**: SQLite database, debug mode
- **Staging**: PostgreSQL, limited logging
- **Production**: PostgreSQL, Redis, full monitoring

## Monitoring and Logging

### Health Checks

- Application health at `/health`
- Database connectivity
- External service availability
- Telegram API accessibility

### Logging

- Structured logging with timestamps
- Error tracking and alerting
- Performance metrics
- User interaction analytics

### Metrics

- Message delivery rates
- Error rates by type
- Response times
- Active user counts

## Security

### Authentication

- Service-to-service authentication via tokens
- Bot token validation for webhooks
- Request rate limiting

### Data Protection

- User data encryption in transit
- Secure credential storage
- GDPR compliance considerations

## Troubleshooting

### Common Issues

1. **Webhook Not Receiving Updates**
   - Check webhook URL configuration
   - Verify SSL certificate validity
   - Confirm bot token is correct

2. **Database Connection Errors**
   - Verify DATABASE_URL format
   - Check database server availability
   - Confirm credentials are correct

3. **Service Communication Failures**
   - Check service URLs and availability
   - Verify authentication tokens
   - Review network connectivity

### Debug Mode

Enable debug mode for development:

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python app.py
```

### Log Analysis

Check application logs for errors:

```bash
# Docker logs
docker-compose logs bot-service

# Application logs
tail -f logs/app.log
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit pull request

### Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write comprehensive docstrings
- Maintain test coverage above 80%

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:

- Create an issue in the repository
- Contact the development team
- Check the troubleshooting guide

## Changelog

### Version 1.0.0

- Initial release
- Complete webhook processing
- User interaction handling
- Background task system
- Comprehensive test suite

