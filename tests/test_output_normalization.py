import pytest

from app.features.submissions.comparison import compare, CompareConfig, ComparisonMode, resolve_mode


@pytest.mark.parametrize(
    "expected, actual, should_pass",
    [
        ("('Alice', 20)", "('Alice', 20)\n", True),
        ("('Alice',20)", "( 'Alice' , 20 )\n", True),
        ("('Alice', 20)", "  (  'Alice',   20  )  ", True),
        ("['Alice', 20]", "['Alice',20]\n", True),
        ("{'name': 'Alice', 'age': 20}", "{'age':20,'name':'Alice'}", True),
        ("('Alice', 20)", "('Bob', 20)", False),
        ("('Alice', 20)", "('Alice', 21)", False),
    ],
)
@pytest.mark.asyncio
async def test_compare_tuples_dicts(expected, actual, should_pass):
    result = await compare(expected, actual)
    assert result.passed is should_pass


@pytest.mark.asyncio
async def test_compare_float_tolerance_pass():
    result = await compare("3.1415926", "3.141593")
    assert result.passed is True


@pytest.mark.asyncio
async def test_compare_float_tolerance_fail():
    cfg = CompareConfig(float_eps=1e-8)
    result = await compare("3.1415926", "3.141593", cfg)
    assert result.passed is False


@pytest.mark.asyncio
async def test_compare_set_order():
    result = await compare("{1, 2, 3}", "{3, 2, 1}")
    assert result.passed is True


@pytest.mark.asyncio
async def test_unicode_normalisation():
    result = await compare("é", "e\u0301")
    assert result.passed is True


@pytest.mark.asyncio
async def test_large_output_hash_pass():
    cfg = CompareConfig(large_output_threshold=16)
    payload = "A" * 32
    result = await compare(payload, payload, cfg)
    assert result.passed is True
    assert result.mode_applied == ComparisonMode.HASH_SHA256


@pytest.mark.asyncio
async def test_large_output_hash_fail():
    cfg = CompareConfig(large_output_threshold=16)
    payload = "A" * 32
    result = await compare(payload, payload[:-1] + "B", cfg)
    assert result.passed is False
    assert result.mode_applied == ComparisonMode.HASH_SHA256


@pytest.mark.asyncio
async def test_compare_mode_override_float_config():
    cfg = CompareConfig(float_eps=1e-9)
    result = await compare(
        "3.0",
        "3.0009",
        cfg,
        mode=ComparisonMode.FLOAT_EPS,
        compare_config={"float_eps": 1e-3},
    )
    assert result.passed is True
    assert result.mode_applied == ComparisonMode.FLOAT_EPS


def test_resolve_mode_invalid_defaults_to_auto():
    assert resolve_mode(None) == ComparisonMode.AUTO
    assert resolve_mode(" ") == ComparisonMode.AUTO
    assert resolve_mode("strict") == ComparisonMode.STRICT
    assert resolve_mode("does_not_exist") == ComparisonMode.AUTO
