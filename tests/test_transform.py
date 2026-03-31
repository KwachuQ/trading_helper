def test_nq_qqq_ratio_precision_4dp():
    nq_close = 21345.25
    qqq_close = 543.67
    ratio = round(nq_close / qqq_close, 4)
    decimals = str(ratio).split(".")[1]
    assert len(decimals) <= 4


def test_vvix_vix_ratio_precision_4dp():
    vvix_close = 98.5
    vix_close = 17.32
    ratio = round(vvix_close / vix_close, 4)
    decimals = str(ratio).split(".")[1]
    assert len(decimals) <= 4


def test_adr_calculation_qqq():
    high = 550.0
    low = 535.5
    adr = round(high - low, 4)
    assert adr == 14.5


def test_adr_calculation_nq():
    high = 21500.75
    low = 21200.25
    adr = round(high - low, 4)
    assert adr == 300.5
