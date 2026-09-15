def test_lcc_cannot_be_confirmed_by_amadeus_only(run_cli):
    assert run_cli('amadeus-can-confirm','LCC') is False
    assert run_cli('amadeus-can-confirm','FULL_SERVICE') is True
