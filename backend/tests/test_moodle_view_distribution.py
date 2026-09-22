import pytest
from lamb.moodle.analytics.view_distribution import display_bins
from lamb.moodle.analytics.view_time import _distribution


@pytest.mark.parametrize('values',[[],[0,0],[1,4,5],list(range(1000)),[0,1,20000]])
def test_display_bins_preserve_population_and_weighted_ranges(values):
    source=_distribution(values)
    bins=display_bins(source)
    assert len(bins)<=21
    assert sum(row['students'] for row in bins)==len(values)
    if not values:
        assert bins==[]
        return
    assert bins[0]=={'lower':0,'upper':0,'students':values.count(0)}
    for row in bins:
        assert row['students']==sum(row['lower']<=value<=row['upper'] for value in values)
    assert all(left['upper']+1==right['lower'] for left,right in zip(bins,bins[1:]))
    assert source==_distribution(values)


@pytest.mark.parametrize('histogram,population',[
    ([{'value':True,'students':1}],1),([{'value':-1,'students':1}],1),
    ([{'value':0,'students':0}],0),([{'value':1,'students':True}],1),
    ([{'value':1,'students':1},{'value':1,'students':1}],2),
    ([{'value':1,'students':1}],2),([{'value':20001,'students':1}],1),
    ([],1001),([],True),
])
def test_invalid_histograms_fail_instead_of_becoming_plausible_bars(histogram,population):
    with pytest.raises(ValueError):
        display_bins({'histogram':histogram,'population_students':population})
