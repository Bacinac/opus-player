import pytest
from pydantic import ValidationError

from opus.api.routers.progress import MOST_AT_ONCE, Report, Seen, _finished, ids_of


@pytest.mark.parametrize(("position", "duration", "credits", "finished"), [
    (100, None, None, False),
    (7150, 7200, None, True),
    (7000, 7200, None, False),
    (170, 180, None, True),
    (150, 180, None, False),
    (6500, 7200, 6480, True),
    (6400, 7200, 6480, False),
])
def test_finished(position, duration, credits, finished):
    assert _finished(position, duration, credits) is finished


def test_ids_of_takes_only_ids():
    assert ids_of("1, 2,-3,x,²,٣,--5,4.5,,7") == [1, 2, -3, 7]
    assert ids_of("99999999999,2147483647,2147483648,-2147483648") == [2147483647, -2147483648]
    assert len(ids_of(",".join(["1"] * (MOST_AT_ONCE + 5)))) == MOST_AT_ONCE


def test_a_report_fits_the_row_it_is_written_to():
    Report(kind="movie", item_id=5, position_s=1.0, surface="desktop")
    with pytest.raises(ValidationError):
        Report(kind="movie", item_id=5, position_s=1.0, surface="x" * 17)
    with pytest.raises(ValidationError):
        Report(kind="movie", item_id=2**31, position_s=1.0)
    with pytest.raises(ValidationError):
        Report(kind="episode", item_id=5, position_s=1.0, parent_id=2**40)


def test_seen_is_a_bounded_list_of_ids():
    Seen(kind="episode", item_ids=[1, 2, 3])
    with pytest.raises(ValidationError):
        Seen(kind="episode", item_ids=[2**31])
    with pytest.raises(ValidationError):
        Seen(kind="episode", item_ids=list(range(MOST_AT_ONCE + 1)))
