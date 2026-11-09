from abhyasa.core.hostapi import HOST_API, host_missing


def test_host_api_is_a_positive_int():
    assert type(HOST_API) is int and HOST_API >= 1


def test_host_missing_says_why_only_when_too_old():
    assert host_missing(HOST_API) == "" and host_missing(0) == ""
    assert host_missing(HOST_API + 1) == f"Abhyasa too old: needs host API {HOST_API + 1}, has {HOST_API}"
