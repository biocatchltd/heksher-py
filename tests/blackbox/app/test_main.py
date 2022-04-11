from pytest import mark


@mark.asyncio
async def test_health_check(heksher_service):
    (await heksher_service.http_client.get('/api/health')).raise_for_status()
    assert heksher_service.postgres_service.is_alive()

