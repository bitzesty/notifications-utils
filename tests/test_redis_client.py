import pytest
from freezegun import freeze_time
from unittest.mock import Mock

from notifications_utils.clients.redis import daily_limit_cache_key
from notifications_utils.clients.redis.redis_client import RedisClient


@pytest.fixture(scope='function')
def mocked_redis_client(app, mocker):
    app.config['REDIS_ENABLED'] = True
    return build_redis_client(app, mocker)


def build_redis_client(app, mocker):
    redis_client = RedisClient()
    redis_client.init_app(app)
    mocker.patch.object(redis_client.redis_store, 'get', return_value=100)
    mocker.patch.object(redis_client.redis_store, 'set')
    mocker.patch.object(redis_client.redis_store, 'hincrby')
    mocker.patch.object(redis_client.redis_store, 'hgetall',
                        return_value={b'template-1111': b'8', b'template-2222': b'8'})
    mocker.patch.object(redis_client.redis_store, 'hmset')
    mocker.patch.object(redis_client.redis_store, 'expire')

    return redis_client


def test_should_not_raise_exception_if_raise_set_to_false(app):
    app.config['REDIS_ENABLED'] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    redis_client.redis_store.get = Mock(side_effect=Exception())
    redis_client.redis_store.set = Mock(side_effect=Exception())
    redis_client.redis_store.incr = Mock(side_effect=Exception())
    assert redis_client.get('test') is None
    assert redis_client.set('test', 'test') is None
    assert redis_client.incr('test') is None


def test_should_raise_exception_if_raise_set_to_true(app):
    app.config['REDIS_ENABLED'] = True
    redis_client = RedisClient()
    redis_client.init_app(app)
    redis_client.redis_store.get = Mock(side_effect=Exception('get failed'))
    redis_client.redis_store.set = Mock(side_effect=Exception('set failed'))
    redis_client.redis_store.incr = Mock(side_effect=Exception('inc failed'))
    with pytest.raises(Exception) as e:
        redis_client.get('test', raise_exception=True)
    assert str(e.value) == 'get failed'
    with pytest.raises(Exception) as e:
        redis_client.set('test', 'test', raise_exception=True)
    assert str(e.value) == 'set failed'
    with pytest.raises(Exception) as e:
        redis_client.incr('test', raise_exception=True)
    assert str(e.value) == 'inc failed'


def test_should_not_call_set_if_not_enabled(mocked_redis_client):
    mocked_redis_client.active = False
    assert not mocked_redis_client.set('key', 'value')
    mocked_redis_client.redis_store.set.assert_not_called()


def test_should_call_set_if_enabled(mocked_redis_client):
    mocked_redis_client.set('key', 'value')
    mocked_redis_client.redis_store.set.assert_called_with('key', 'value', None, None, False, False)


def test_should_not_call_get_if_not_enabled(mocked_redis_client):
    mocked_redis_client.active = False
    mocked_redis_client.get('key')
    mocked_redis_client.redis_store.get.assert_not_called()


def test_should_call_get_if_enabled(mocked_redis_client):
    assert mocked_redis_client.get('key') == 100
    mocked_redis_client.redis_store.get.assert_called_with('key')


def test_should_build_cache_key_service_and_action(sample_service):
    with freeze_time("2016-01-01 12:00:00.000000"):
        assert daily_limit_cache_key(sample_service.id) == '{}-2016-01-01-count'.format(sample_service.id)


def test_decrement_hash_value_should_decrement_value_by_one_for_key(mocked_redis_client):
    key = '12345'
    value = "template-1111"

    mocked_redis_client.decrement_hash_value(key, value, -1)
    mocked_redis_client.redis_store.hincrby.assert_called_with(key, value, -1)


def test_incr_hash_value_should_increment_value_by_one_for_key(mocked_redis_client):
    key = '12345'
    value = "template-1111"

    mocked_redis_client.increment_hash_value(key, value)
    mocked_redis_client.redis_store.hincrby.assert_called_with(key, value, 1)


def test_get_all_from_hash_returns_hash_for_key(mocked_redis_client):
    key = '12345'
    assert mocked_redis_client.get_all_from_hash(key) == {b'template-1111': b'8', b'template-2222': b'8'}
    mocked_redis_client.redis_store.hgetall.assert_called_with(key)


def test_set_hash_and_expire(mocked_redis_client):
    key = 'hash-key'
    values = {'key': 10}
    mocked_redis_client.set_hash_and_expire(key, values, 1)
    mocked_redis_client.redis_store.hmset.assert_called_with(key, values)
    mocked_redis_client.redis_store.expire.assert_called_with(key, 1)