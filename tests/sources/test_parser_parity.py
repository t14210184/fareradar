from external_worker import worker as ew


def test_external_worker_and_cloud_parser_parity(run_cli):
    text='TPE-KIX 尊榮虎 樂虎卡 APP限定 限時特價 NT$3,999 優惠碼 SALE 限來回 指定航班 MM627/MM629'
    cloud=run_cli('extract-promo-text',{'text':text,'market':'TW'})
    edge=ew.structured_signal(text,'source-1')['structured_payload']
    assert cloud is not None
    for key in ('routes','prices','promo_code','keywords','member_requirement','channel_requirement','eligible_flight_numbers','required_roundtrip','coupon_required','sales_currency'):
        assert cloud[key] == edge[key]
    assert cloud['market'] == edge['market'] == 'TW'
