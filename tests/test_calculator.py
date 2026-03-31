import pytest


def convert_levels(input_str: str, ratio: float) -> str:
    """Parse QQQ levels and convert to NQ levels using the given ratio."""
    tokens = [t.strip() for t in input_str.split(",")]
    if len(tokens) % 2 != 0:
        raise ValueError("Expected even number of comma-separated tokens")

    output_parts = []
    for i in range(0, len(tokens), 2):
        label = tokens[i]
        qqq_val = float(tokens[i + 1])
        nq_val = qqq_val * ratio
        if nq_val == int(nq_val):
            formatted = str(int(nq_val))
        else:
            formatted = f"{nq_val:.2f}"
        output_parts.append(f"{label}, {formatted}")
    return ", ".join(output_parts)


def test_parse_input_string():
    tokens = [t.strip() for t in "Call Resistance, 630, Put Support, 560".split(",")]
    assert tokens == ["Call Resistance", "630", "Put Support", "560"]


def test_conversion_formula():
    ratio = 24750 / 630  # 39.285714...
    result = 630 * ratio
    assert abs(result - 24750.0) < 0.01


def test_output_format():
    result = convert_levels("Call Resistance, 630, Put Support, 560", 39.285714)
    parts = result.split(", ")
    assert parts[0] == "Call Resistance"
    assert parts[2] == "Put Support"


def test_rounding_whole_number():
    # 630 * 39.285714... ≈ 24750.0 → should be integer
    ratio = 24750 / 630
    result = convert_levels("HVL, 630", ratio)
    assert result == "HVL, 24750"


def test_rounding_decimal():
    ratio = 41.45
    result = convert_levels("1D Min, 548.33", ratio)
    # 548.33 * 41.45 = 22728.28...
    assert "1D Min, 22728.28" == result


def test_odd_tokens_raises():
    with pytest.raises(ValueError):
        convert_levels("Call Resistance, 630, Put Support", 39.0)


def test_full_example():
    ratio = 24750 / 630  # ~39.2857
    input_str = "Call Resistance, 630, Put Support, 560"
    result = convert_levels(input_str, ratio)
    parts = [t.strip() for t in result.split(",")]
    # Check that numeric parts are present and reasonable
    assert float(parts[1]) == pytest.approx(24750, abs=1)
    assert float(parts[3]) == pytest.approx(22000, abs=1)
